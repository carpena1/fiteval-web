from . import (config_cb, data_cb, multirun_cb, run_cb, uncertainty_cb,
               views_cb)


def register_all(app) -> None:
    data_cb.register(app)
    run_cb.register(app)
    views_cb.register(app)
    config_cb.register(app)
    uncertainty_cb.register(app)
    multirun_cb.register(app)
