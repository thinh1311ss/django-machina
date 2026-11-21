"""Model lookup delegates to Django's application registry whenever it is ready.
During application population, the registry may know an application before its
models have been imported. In that narrow window, lookup imports the configured
models module and then requests the registered model with the original labels.
This preserves the application's configured package and model identity instead
of importing a class from an assumed module path. An application that replaces
its model definitions can therefore participate in the same lookup sequence.
Calls made before applications are ready still surface the registry exception.
The lookup helpers do not initialize Django or retry application population.
They do not create database connections, execute queries or instantiate models.
Code that needs an instance should resolve its model first and use its manager.
The availability check uses the same application and model labels as lookup.
"""

from importlib import import_module

from django.apps import apps
from django.apps.config import MODELS_MODULE_NAME
from django.core.exceptions import AppRegistryNotReady


# The following is mainly inspired from the model loading tools provided
# by django-oscar to handle overridable model classes.


def get_model(app_label, model_name):
    """ Given an app label and a model name, returns the corresponding model class. """
    try:
        return apps.get_model(app_label, model_name)
    except AppRegistryNotReady:
        if apps.apps_ready and not apps.models_ready:
            # If the models module of the considered app has not been loaded yet,
            # we try to import it manually in order to retrieve the model class.
            # This trick is usefull in order to get the model class during the
            # ``apps.populate()`` call and the execution of related methods of AppConfig
            # instances (eg. ``ready``).

            # Firts, the config of the consideration must be retrieved
            app_config = apps.get_app_config(app_label)
            # Then the models module is manually imported
            import_module('%s.%s' % (app_config.name, MODELS_MODULE_NAME))
            # Finally, tries to return the registered model class
            return apps.get_registered_model(app_label, model_name)
        else:
            raise


def is_model_registered(app_label, model_name):
    """ Checks whether the given model is registered or not.

    It is usefull to prevent Machina models for being registered if they are overridden by local
    apps.

    """
    try:
        apps.get_registered_model(app_label, model_name)
    except LookupError:
        return False
    else:
        return True


def model_factory(abstract_class):
    """ Given an abstract class, constructs the model that inherits from this class only if a model
        with the same (app label, model name) was not already in the app registry.
    """
    app_label = abstract_class.Meta.app_label
    model_name = abstract_class.__name__.replace('Abstract', '')

    if not is_model_registered(app_label, model_name):
        return type(str(model_name), (abstract_class, ), {'__module__': __name__, })
