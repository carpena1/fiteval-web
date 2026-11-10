"""fiteval_core - computation engine of FITEVAL (no web dependencies).

Python port of the FITEVAL v4.0 MATLAB application
(c) 2011 Axel Ritter & Rafael Munoz-Carpena.
Ref.: Ritter and Munoz-Carpena. 2013. J. Hydrol. 480,
doi:10.1016/j.jhydrol.2012.12.004
"""

__version__ = "4.0.0"

from .config import FitevalConfig, read_config, write_config  # noqa: F401
