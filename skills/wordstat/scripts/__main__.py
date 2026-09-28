"""Run the native Wordstat command line interface."""

import sys

sys.dont_write_bytecode = True

from .environment import load_windows_user_environment
from .cli import main


load_windows_user_environment()
raise SystemExit(main())
