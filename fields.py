from django import forms

import display

class MultipleChoiceField(forms.MultipleChoiceField):
    '''Override the built-in MultipleChoiceField to allow 
    selection of only one item'''

    def clean(self, value):
        if isinstance(value, unicode) or isinstance(value, str):
            return [value]

        return value

