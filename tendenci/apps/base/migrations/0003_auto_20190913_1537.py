# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-09-13 15:37
from __future__ import unicode_literals

from django.db import migrations


def update_jquery_in_theme(apps, schema_editor):
    """
    Upgrade jquery for templates and js in theme's directory.
    """
    import re
    import os
    import sys
    from collections import OrderedDict
    from tendenci.apps.theme.utils import get_theme_root
    
    theme_dir = get_theme_root()
    # Check base.html
    file_path = '{}/templates/base.html'.format(theme_dir)
    if os.path.isfile(file_path):
        content = ''
        file_changed = False
        with open(file_path, 'r') as f:
            content = f.read()
            p = r'({0}[\d\D\s\S\w\W]*?)({1})([\d\D\s\S\w\W]*?{2})'.format(re.escape('{% block jquery_script %}'),
            re.escape('<script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/2.1.1/jquery.min.js"></script>'),
            re.escape('{% endblock jquery_script %}'))
            if re.search(p, content):
                content = re.sub(p, r'\1{}\3'.format('<script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/3.4.1/jquery.min.js"></script>'),
                                 content)
                file_changed = True 

        if file_changed:
            with open(file_path, 'w') as f:
                f.write(content)

    # Update custom templates
    items_find_replace = OrderedDict([('.click(function', '.on("click", function'),
                                        ('.mouseenter(function', '.on("mouseenter", function'),
                                        ('.removeAttr(\'multiple\')', ".prop('multiple', false )"),
                                        ('.removeAttr(\'disabled\')', ".prop('disabled', false )"),
                                        ('.removeAttr(\'checked\')', ".prop('checked', false )"),
                                        ('.removeAttr(\'required\')', ".prop('required', false )"),
                                        ('.removeAttr(\'id\')', ".prop('id', false )"),
                                        #('.unbind(', '.off('),
                                        #('.bind(', '.on('),
                                        ('$.parseJSON', 'JSON.parse'),
                                        ('.change(function', '.on("change", function'),
                                        ('.submit(function', '.on("submit", function'),
                                        ('.keyup(function', '.on("keyup", function'),
                                        ('.keydown(', '.on("keydown", '),
                                        ('.blur(', '.on("blur", '),
                                        ('.focus()', '.trigger("focus")'),
                                        ('.focus(function', '.on("focus", function'),
                                        ('.unload(', '.on("unload", '),
                                        ('.load(', '.on("load", '),])
    items_to_check = items_find_replace.keys()
    theme_templatges_dir = os.path.join(theme_dir, 'templates')
    #theme_media_dir = os.path.join(theme_dir, 'media')
    for directory in [theme_templatges_dir,]:
        for root, dirs, files in os.walk(directory):
            for file_name in files:
                if os.path.splitext(file_name)[1] in ('.html', '.js'):
                    file_path = os.path.join(root, file_name)
                    file_changed = False
                    with open(file_path, 'r') as f:
                        try:
                            content = f.read()
                        except:
                            print("Error on reading file {}:".format(file_path), sys.exc_info()[0])
                            raise
                        for item in items_to_check:
                            if item in content:
                                file_changed = True
                                break
                        for k, v in items_find_replace.items():
                            content = content.replace(k, v)
                            
                    if file_changed:
                        with open(file_path, 'w') as f:
                            f.write(content)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_auto_20150804_1545'),
    ]

    operations = [
        migrations.RunPython(update_jquery_in_theme)
    ]
