# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).

import os

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window. Set to False before
# distributing the add-in.
DEBUG = True

# Gets the name of the add-in from the name of the folder the py file is in.
# Used to build unique internal IDs for UI elements.
ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = 'fusion360football'
