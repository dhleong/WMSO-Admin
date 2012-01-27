
from google.appengine.ext import db
from google.appengine.ext.db import djangoforms

class ModelForm(djangoforms.ModelForm):

    def create(self, commit=True, key_name=None, parent=None):
        """Save this form's cleaned data into a new model instance.

        Args:
          commit: optional bool, default True; if true, the model instance
            is also saved to the datastore.
          key_name: the key_name of the new model instance, default None
          parent: the parent of the new model instance, default None

        Returns:
          The model instance created by this call.
        Raises:
          ValueError if the data couldn't be validated.
        """
        if not self.is_bound:
            raise ValueError('Cannot save an unbound form')
        opts = self._meta
        instance = self.instance
        if self.instance:
            raise ValueError('Cannot create a saved form')
        if self.errors:
            raise ValueError("The %s could not be created because the data didn't "
                           'validate.' % opts.model.kind())
        cleaned_data = self._cleaned_data()
        converted_data = {}
        for name, prop in opts.model.properties().iteritems():
            value = cleaned_data.get(name)
            if value is not None:
                converted_data[name] = prop.make_value_from_form(value)
        try:
            instance = opts.model(key_name=key_name, parent=parent, **converted_data)
            self.instance = instance
        except db.BadValueError, err:
            raise ValueError('The %s could not be created (%s)' %
                           (opts.model.kind(), err))
        if commit:
            instance.put()
        return instance


