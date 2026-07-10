import os
import traceback

import adsk
import adsk.core
import adsk.fusion

from ...lib import fusionAddInUtils as futil
from ...lib import ball_builder
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_buildFootball'
CMD_NAME = 'Football'
CMD_Description = 'Builds a football (truncated icosahedron) as 32 printable pentagon/hexagon panels.'

IS_PROMOTED = True

WORKSPACE_ID = 'FusionSolidEnvironment'
# Live in the Solid > Create menu, alongside the other solid-creation tools.
PANEL_ID = 'SolidCreatePanel'

# Folder with the command's button icons (16x16.png, 32x32.png, 64x64.png).
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Command input IDs.
ID_HEXAGON_SIDE = 'hexagonSide'
ID_FACE_DEEP = 'faceDeep'
ID_TOLERANCE = 'tolerance'
ID_EXTERIOR_STYLE = 'exteriorStyle'
ID_PENTAGON_COLOR_GROUP = 'pentagonColorGroup'
ID_PENTAGON_R = 'pentagonColorR'
ID_PENTAGON_G = 'pentagonColorG'
ID_PENTAGON_B = 'pentagonColorB'
ID_HEXAGON_COLOR_GROUP = 'hexagonColorGroup'
ID_HEXAGON_R = 'hexagonColorR'
ID_HEXAGON_G = 'hexagonColorG'
ID_HEXAGON_B = 'hexagonColorB'

EXTERIOR_FLAT = 'Flat'
EXTERIOR_ROUNDED = 'Rounded'

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


def start():
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    futil.add_handler(cmd_def.commandCreated, command_created)

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    control = panel.controls.addCommand(cmd_def)
    control.isPromoted = IS_PROMOTED


def stop():
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    if command_control:
        command_control.deleteMe()
    if command_definition:
        command_definition.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    inputs = args.command.commandInputs

    inputs.addValueInput(
        ID_HEXAGON_SIDE, 'Hexagon side', 'mm', adsk.core.ValueInput.createByString('44 mm'))
    inputs.addValueInput(
        ID_FACE_DEEP, 'Face deep', 'mm', adsk.core.ValueInput.createByString('5 mm'))
    inputs.addValueInput(
        ID_TOLERANCE, 'Print tolerance (gap)', 'mm',
        adsk.core.ValueInput.createByString('0 mm'))

    exterior_input = inputs.addDropDownCommandInput(
        ID_EXTERIOR_STYLE, 'External face', adsk.core.DropDownStyles.TextListDropDownStyle)
    exterior_input.listItems.add(EXTERIOR_FLAT, True)
    exterior_input.listItems.add(EXTERIOR_ROUNDED, False)

    pentagon_group = inputs.addGroupCommandInput(ID_PENTAGON_COLOR_GROUP, 'Pentagon color')
    _add_rgb_inputs(pentagon_group.children, ID_PENTAGON_R, ID_PENTAGON_G, ID_PENTAGON_B, (0, 0, 0))

    hexagon_group = inputs.addGroupCommandInput(ID_HEXAGON_COLOR_GROUP, 'Hexagon color')
    _add_rgb_inputs(hexagon_group.children, ID_HEXAGON_R, ID_HEXAGON_G, ID_HEXAGON_B, (255, 255, 255))

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


def _add_rgb_inputs(inputs, id_r, id_g, id_b, default_rgb):
    r, g, b = default_rgb
    inputs.addIntegerSpinnerCommandInput(id_r, 'Red', 0, 255, 1, r)
    inputs.addIntegerSpinnerCommandInput(id_g, 'Green', 0, 255, 1, g)
    inputs.addIntegerSpinnerCommandInput(id_b, 'Blue', 0, 255, 1, b)


def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs

    hexagon_side_cm = inputs.itemById(ID_HEXAGON_SIDE).value
    face_deep_cm = inputs.itemById(ID_FACE_DEEP).value
    tolerance_cm = inputs.itemById(ID_TOLERANCE).value
    exterior_style = inputs.itemById(ID_EXTERIOR_STYLE).selectedItem.name
    rounded = exterior_style == EXTERIOR_ROUNDED

    pentagon_rgb = (
        inputs.itemById(ID_PENTAGON_R).value,
        inputs.itemById(ID_PENTAGON_G).value,
        inputs.itemById(ID_PENTAGON_B).value,
    )
    hexagon_rgb = (
        inputs.itemById(ID_HEXAGON_R).value,
        inputs.itemById(ID_HEXAGON_G).value,
        inputs.itemById(ID_HEXAGON_B).value,
    )

    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        ui.messageBox('No active Fusion design. Create or open a design first.')
        return

    progress = ui.createProgressDialog()
    progress.show(CMD_NAME, 'Building panel %v of %m...', 0, 32, 0)

    def on_progress(done, total):
        progress.progressValue = done
        adsk.doEvents()

    try:
        bodies = ball_builder.build_football(
            design, hexagon_side_cm, face_deep_cm, rounded,
            pentagon_rgb, hexagon_rgb, tolerance_cm=tolerance_cm,
            progress_callback=on_progress)
    except:
        futil.log(f'{CMD_NAME} failed:\n{traceback.format_exc()}', adsk.core.LogLevels.ErrorLogLevel)
        ui.messageBox(f'Failed to build the football:\n{traceback.format_exc()}')
        return
    finally:
        progress.hide()

    pentagon_count = sum(1 for b in bodies if b.name.startswith('Pentagon'))
    hexagon_count = sum(1 for b in bodies if b.name.startswith('Hexagon'))
    ui.messageBox(
        f'Football built: {pentagon_count} pentagons + {hexagon_count} hexagons '
        f'({len(bodies)} bodies total).')


def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    inputs = args.inputs
    hexagon_side = inputs.itemById(ID_HEXAGON_SIDE)
    face_deep = inputs.itemById(ID_FACE_DEEP)
    tolerance = inputs.itemById(ID_TOLERANCE)

    valid = (
        hexagon_side.value > 0
        and face_deep.value > 0
        and face_deep.value < hexagon_side.value
        and tolerance.value >= 0
        and tolerance.value < hexagon_side.value
    )
    args.areInputsValid = valid


def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []
