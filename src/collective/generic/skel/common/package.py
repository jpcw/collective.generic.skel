import sys
import os
import re

from paste.script.templates import var
from paste.script.templates import Template

from collective.generic.skel.buildout import (
    common,
    plone3,
    plone4,
    plone41,
    plone42,
    plone43,
    #plone44,
    #django,
    pyramid,
)


boolify = common.boolify
running_user = common.running_user
re_flags = common.re_flags


REGENERATE_MSG = """
Lot of files generated by the collective.generic packages
will try to load user defined objects in user specific files.
The final goal is to regenerate easyly the test infrastructure on
templates updates without impacting user-specific test boilerplate.
We do not use paster local commands (insert/update) as it cannot
determine witch is specific or not and we prefer to totally separe
generated stuff and what is user specific
"""
REGENERATE_FILE = """
If you need to edit something in this file, you must have better to do it in:
"""

SHARP_LINE = '#' * 80

REGENERATE_OBJECTS = """
Objects that you can edit and get things overidden are:
"""

p3_themes = {
    'default': 'Plone Default',
}
p4_themes = {
    'sunburst': 'Sunburst Theme',
    'classic': 'Plone Classic Theme',
}


class Package(Template):
    """
    Package template to do a double namespace egg.
    Althout it prentends to do that, it is a base for sub templates
    that need to have all sort
    of variables defined. That's why there is some curious plone bits there.
    """
    _template_dir = 'tmpl'
    summary = "A Generic double namespaced egg."
    egg_plugins = ['PasteScript']
    use_cheetah = True
    pyver = '2.7'
    vars = [
        var('namespace', 'Namespace', default='%(namespace)s'),
        var('nested_namespace', 'Nested Namespace', default='%(package)s'),
        var('version', 'Version', default='1.0'),
        var('author', 'Author', default=running_user,),
        var('author_email', 'Email', default='%s@%s' % (running_user,
                                                        'localhost')),
        var('uri', 'URL of checkout', default=''),
        var('homepage', 'URL of homepage', default=''),
        var('scm_type', 'checkout type', default='git'),
        var('description', 'One-line description of the package',
            default='Project %s'),
        var('keywords', 'Space-separated keywords/tags'),
        var('license_name', 'License name', default='GPL'),
        var('project_name',
            'Project namespace name (to override the first '
            'given project name forced by some '
            'derivated templates, left empty in doubt)', default=''),
    ]

    def run(self, command, output_dir, vars):
        self.boolify(vars)
        self.pre(command, output_dir, vars)
        # may we have register variables ?
        if self.output_dir:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            output_dir = self.output_dir
        if not os.path.isdir(output_dir):
            raise Exception('%s is not a directory' % output_dir)
        self.write_files(command, self.output_dir, vars)
        self.post(command, output_dir, vars)
        if not command.options.quiet:
            print "-" * 79
            print "The template has been generated in %s" % self.output_dir
            print "-" * 79

    def boolify(self, d, keys=None):
        return boolify(d, keys)

    def read_vars(self, command=None):
        vars = Template.read_vars(self, command)
        infos = {}
        project = ''
        if command:
            project = command.args[0]
        if '.' in project:
            try:
                pdata = project.split('.')
                infos['namespace'] = pdata[0]
                infos['nested_namespace'] = pdata[1]
                infos['project'] = pdata[2]
                if getattr(self, 'project', None):
                    infos['project'] = self.project
            except:
                try:
                    # user may try to only give namespace/project
                    # as he is doing a template with a predefined project.
                    pdata = project.split('.')
                    infos['nested_namespace'] = pdata[0]
                    infos['project'] = pdata[1]
                except:
                    print (
                        "Your project name must either in the form "
                        "\"project\" or \"namespace.package.project\""
                    )
                    print "Invalid name: '%s'." % project
                    sys.exit(255)
            self.project = infos['project']
        else:
            infos['namespace'] = ''
            infos['nested_namespace'] = ''
            infos['project'] = project
            self.project = getattr(self, 'project', infos['project'])
        ndot = '.'
        nsdot = '.'
        if not infos['namespace']:
            ndot = ''
        if not infos['nested_namespace']:
            nsdot = ''

        self.dn = '%s%s%s%s%s' % (infos['namespace'], ndot,
                                  infos['nested_namespace'],
                                  nsdot,
                                  self.project)
        for i, var in enumerate(vars[:]):
            if var.name == 'plone_version':
                plone_v = getattr(self, 'plone_version', None)
                if plone_v:
                    vars[i].default = plone_v
            if (
                var.name == 'description'
                and '%s' in vars[i].default and command
            ):
                vars[i].default = vars[i].default % command.args[0]
            for name in infos.keys():
                if var.name == name:
                    vars[i].default = infos[name]
            if var.name == 'project_name':
                vars[i].default = self.project
            if var.name == 'homepage':
                if '%s' in vars[i].default:
                    vars[i].default = vars[i].default % self.dn
        # this allow to fix the egg-info bug
        # As we are using namespaces constructed, and args[0]
        # was maybe not yet ready
        # by default paster will fail to resolve the distrbition name.
        from paste.script import pluginlib
        if not 'old_egg_info_dir' in dir(pluginlib):
            pluginlib.old_egg_info_dir = pluginlib.egg_info_dir
            self.module = self.__class__.__module__

            def wrap_egg_info_dir(c, n):
                print "%s" % (
                    "%s> Monkey patching egg_info_dir "
                    "to resolve good distro name: "
                    "'%s' (old was '%s')" % (
                        self.module, self.dn, n
                    )
                )
                ret = None
                try:
                    ret = pluginlib.old_egg_info_dir(c, self.dn)
                except Exception:
                    try:
                        os.makedirs(os.path.join(
                            c,
                            "src",
                            "%s.egg-info" % self.dn
                        ))
                    except Exception:
                        pass
                    try:
                        ret = pluginlib.old_egg_info_dir(c, self.dn)
                    except Exception:
                        raise
                return ret
            pluginlib.egg_info_dir = wrap_egg_info_dir
        return vars

    def pre(self, command, output_dir, vars):
        Template.pre(self, command, output_dir, vars)
        if not vars['project_name']:
            vars['project_name'] = vars['project']
        else:
            self.project = vars['project_name']
        vars['project'] = self.project
        vars['ndot'] = '.'
        vars['nunderscore'] = '_'
        vars['nsunderscore'] = '_'
        if not vars['namespace']:
            vars['ndot'] = ''
            vars['nunderscore'] = ''
        vars['nsdot'] = '.'
        if not vars['nested_namespace']:
            vars['nsdot'] = ''
            vars['nsunderscore'] = ''
        vars['hr'] = SHARP_LINE
        vars['generate_msg'] = REGENERATE_MSG % vars
        vars['generate_file'] = REGENERATE_FILE % vars
        vars['generate_objects'] = REGENERATE_OBJECTS % vars
        vars['pdn'] = self.dn = '%s%s%s%s%s' % (
            vars['namespace'], vars['ndot'],
            vars['nested_namespace'], vars['nsdot'],
            vars['project']
        )
        vars['PdN'] = '%s%s%s' % (
            vars['namespace'].capitalize(),
            vars['nested_namespace'].capitalize(),
            vars['project'].capitalize()
        )
        vars['P_D_N'] = '%s%s%s' % (
            ((True == bool(vars['namespace'].upper()))
             and '%s_' % vars['namespace'].upper() or ''),
            ((True == bool(vars['nested_namespace'].upper()))
             and '%s_' % vars['nested_namespace'].upper() or ''),
            vars['project'].upper()
        )

        if not 'opt_deps' in vars:
            vars['opt_deps'] = " ".join([
                'libxml2-2.7',
                'libxslt-1.1',
                'py-libxml2-2.7',
                'py-libxslt-1.1',
                'pil-1.1.7',
                'libiconv-1.12',
                'openssl-1',
                'python-2.7',
            ])
        if not 'pyver' in vars:
            vars['pyver'] = self.pyver

        self.output_dir = os.path.join(command.options.output_dir)

    def post(self, command, output_dir, vars):
        Template.post(self, command, output_dir, vars)
        isolated_init = os.path.join(output_dir, 'src', '__init__.py')
        isolated_init2 = os.path.join(
            output_dir,
            '%s%s%s%s%s' % (
                vars['namespace'],
                vars['ndot'],
                vars['nested_namespace'],
                vars['nsdot'],
                vars['project_name'],
            ),
            'src', '__init__.py'
        )
        for i in [isolated_init2, isolated_init]:
            if os.path.exists(i) and (
                not bool(vars['namespace'])
                or not bool(vars['nested_namespace'])
            ):
                os.remove(i)

borrowed_vars = [re.compile('with_ploneproduct.*'),
                 re.compile('with_binding.*'),
                 re.compile('with_egg.*'),
                 re.compile('address'),
                 re.compile('http_port'),
                 re.compile('uri'),
                 re.compile('scm_type'),
                 re.compile('opt_deps'),
                 re.compile('inside_minitage'),
                 re.compile('smtp.*'),
                 re.compile('with_database.*')]

plone_vars = Package.vars + [
    var('with_generic', 'with_generic', default='n',)]
excluded_vars = []
p3_vars = []
p4_vars = []
p41_vars = []
p41_vars = []
p42_vars = []
p43_vars = []
p44_vars = []
ppackage_vars = []
django_vars = []
pyramid_vars = []
items = (
    (p3_vars, plone3.Template),
    (p4_vars, plone4.Template),
    (p41_vars, plone41.Template),
    (p42_vars, plone42.Template),
    (p43_vars, plone43.Template),
    (ppackage_vars, plone41.Template),
    #(p44_vars, plone44.Template),
    #(django_vars, django.Template),
    #(pyramid_vars, pyramid.Template),
)

for vars, template in items:
    for cvar in template.vars:
        found = False
        bv = borrowed_vars[:]
        for sre in bv:
            if sre.match(cvar.name) and not found:
                found = True
                vars.append(cvar)
                #if cvar.name.startswith('with_ploneproduct'):
                #    vars.append(
                #        var(
                #            cvar.name.replace(
                #                'ploneproduct',
                #                'autoinstall_ploneproduct'
                #            ),
                #            description = cvar.description,
                #            default = 'y'
                #        )
                #    )
                #    break


class MinitagePackage(Package):
    python = 'python-2.6'
    pyver = python[-3:]

    def load_plone_vars(self, command, output_dir, vars):
        eggs_mappings = getattr(self.paster_template, 'eggs_mappings', {})
        zcml_mappings = getattr(self.paster_template, 'zcml_mappings', {})
        zcml_loading_order = getattr(self.paster_template,
                                     'zcml_loading_order', {})
        qi_mappings = getattr(self.paster_template, 'qi_mappings', {})
        qi_hidden_mappings = getattr(self.paster_template,
                                     'qi_hidden_mappings', {})
        gs_mappings = getattr(self.paster_template, 'gs_mappings', {})
        z2products = getattr(self.paster_template, 'z2products', {})
        z2packages = getattr(self.paster_template, 'z2packages', {})
        versions_mappings = getattr(self.paster_template,
                                    'versions_mappings', {})
        checked_versions_mappings = getattr(self.paster_template,
                                            'checked_versions_mappings', {})
        # do we need some pinned version
        vars['plone_versions'] = {}
        addon = 'Addon' in self.__class__.__name__
        pin_added = []
        if not addon:
            for var in versions_mappings:
                tmp, found = [], False
                vmap = versions_mappings[var]
                vmap.sort()
                for pin in vmap:
                    if not pin in pin_added:
                        pin_added.append(pin)
                        tmp.append(pin)
                        found = True
                if found:
                    if not var in vars['plone_versions']:
                        vars['plone_versions'][var] = []
                    vars['plone_versions'][var].extend(tmp)

        for var in checked_versions_mappings:
            if vars.get(var, False):
                tmp, found = [], False
                vmap = checked_versions_mappings[var].keys()
                vmap.sort()
                for pin in vmap:
                    if not pin in pin_added:
                        pin_added.append(pin)
                        tmp.append((pin, checked_versions_mappings[var][pin]))
                        found = True
                if found:
                    if not var in vars['plone_versions']:
                        vars['plone_versions'][var] = []
                    vars['plone_versions'][var].extend(tmp)

        vars['python_eggs'] = []
        vars['python_eggs_mapping'] = {}
        for var in eggs_mappings:
            if vars.get(var, None):
                for e in eggs_mappings[var]:
                    if not e in vars['python_eggs']:
                        vars['python_eggs'].append(e)
                        if not var in vars['python_eggs_mapping']:
                            vars['python_eggs_mapping'][var] = []
                        vars['python_eggs_mapping'][var].append(e)
        if self.paster_template == pyramid.Template:
            for e in pyramid.base_pyramid_eggs:
                if not e in vars['python_eggs']:
                    vars['python_eggs'].append(e)
                    if not var in vars['python_eggs_mapping']:
                        vars['python_eggs_mapping'][var] = []
                    vars['python_eggs_mapping'][var].append(e)

        vars['products'], vars['tested_products'] = [], []
        # quick install / appconfig
        if not "qi" in vars:
            vars["qi"] = {}
        for key in qi_mappings:
            if vars.get(key, False):
                if not key in vars["qi"]:
                    vars["qi"][key] = []
                #aikey = key.replace('ploneproduct',
                #                    'autoinstall_ploneproduct')
                if True:  # vars.get(aikey, False):
                    vars["qi"][key].extend(
                        [i['name'] for i in qi_mappings[key]])
                else:
                    vars["qi"][key].extend(
                        ["     #'%s'," % i['name'] for i in qi_mappings[key]]
                    )
        # quick install / appconfig
        if not "hqi" in vars:
            vars["hqi"] = {}
        for key in qi_hidden_mappings:
            if vars.get(key, False):
                if not key in vars["hqi"]:
                    vars["hqi"][key] = []
                #aikey = key.replace('ploneproduct',
                #                    'autoinstall_ploneproduct')
                if True:  # vars.get(aikey, False):
                    vars["hqi"][key].extend(qi_hidden_mappings[key])
                else:
                    vars["hqi"][key].extend(
                        ["     #'%s'," % i for i in qi_hidden_mappings[key]]
                    )

        # Zope2 new zope products
        if not "z2packages" in vars:
            vars["z2packages"] = {}
        for key in z2packages:
            if vars.get(key, False):
                if not key in vars["z2packages"]:
                    vars["z2packages"][key] = []
                #aikey = key.replace('ploneproduct',
                #                    'autoinstall_ploneproduct')
                if True:  # vars.get(aikey, False):
                    vars["z2packages"][key].extend(z2packages[key])
                else:
                    vars["z2packages"][key].extend(
                        ["#%s" % i for i in z2packages[key]]
                    )

        # Zope2 old school products
        if not "z2products" in vars:
            vars["z2products"] = {}
        for key in z2products:
            if vars.get(key, False):
                if not key in vars["z2products"]:
                    vars["z2products"][key] = []
                # a zope2 product must not have its namespace
                # in the ztc.installProduct call
                if True:  # vars.get(aikey, False):
                    vars["z2products"][key].extend([i.replace('Products.', '')
                                                    for i in z2products[key]])
                else:
                    vars["z2products"][key].extend(
                        ["#%s" % i.replace('Products.', '')
                         for i in z2products[key]]
                    )

        def zcmlsort(obja, objb):
            apackage = re.sub('^#', '', obja[0]).strip()
            bpackage = re.sub('^#', '', objb[0]).strip()
            aslug = obja[1].strip()
            bslug = objb[1].strip()
            aorder = zcml_loading_order.get((apackage, aslug), 50000)
            border = zcml_loading_order.get((bpackage, bslug), 50000)
            return aorder - border

        # Zope2 old school products
        if not "zcml" in vars:
            vars["zcml"] = []
        seen = []
        for key in zcml_mappings:
            if vars.get(key, False):
                if True:  # vars.get(aikey, False):
                    for i in zcml_mappings[key]:
                        if not i in seen:
                            vars["zcml"].append(i)
                            seen.append(i)
                else:
                    for i in zcml_mappings[key]:
                        if not i in seen:
                            vars["zcml"].append(("#%s" % i[0], i[1]))
                            seen.append(i)

        # generic setup
        vars['gs'] = []
        gsk = gs_mappings.keys()
        gsk.sort(lambda x, y: x[2] - y[2])
        for k in gsk:
            for o in gs_mappings[k]:
                if vars.get(o, False):
                    if not k in vars['gs']:
                        vars['gs'].append(k)

        vars['zcml'].sort(zcmlsort)
        # add option marker
        for option in zcml_mappings:
            for p in zcml_mappings[option]:
                packages = [p, ('#%s' % p[0], p[1])]
                for package in packages:
                    if package in vars['zcml']:
                        i = vars['zcml'].index(package)
                        vars['zcml'][i:i] = ['%s' % option]

        # gather python moduloes to import
        vars['py_modules'], imported_modules = {}, []
        for v in vars['z2packages']:
            found = False
            for w in vars["z2packages"][v]:
                if not w in imported_modules:
                    if not v in vars['py_modules']:
                        vars['py_modules'][v] = []
                    vars['py_modules'][v].append(w)
                    if not w in vars['py_modules'][v]:
                        imported_modules.append(w)

        # normallly thz zope products are needed only if they need zcml slugs.
        #for v in vars['z2packages']:
        #     found = False
        #     for w in vars["z2packages"][v]:
        #         if not w in imported_modules:
        #             if not v in vars['py_modules']:
        #                 vars['py_modules'][v] = []
        #             vars['py_modules'][v].append(w)
        #             imported_modules.append(w)

        opt = '#default'
        for v in vars['zcml']:
            if isinstance(v, basestring):
                opt = v
            if not isinstance(v, basestring):
                w = v[0]
                if not w in imported_modules:
                    if not opt in vars['py_modules']:
                        vars['py_modules'][opt] = []
                    if not w in vars['py_modules'][opt]:
                        vars['py_modules'][opt].append(w)

    def pre(self, command, output_dir, vars):
        Package.pre(self, command, output_dir, vars)
        self.load_plone_vars(command, output_dir, vars)


class PlonePackage(MinitagePackage):
    plone_version = None
    paster_template = plone41.Template
    vars = plone_vars + ppackage_vars

    def __init__(self, *args, **kwargs):
        Template.__init__(self, *args, **kwargs)
        self.plone_version = self.paster_template.packaged_version
        self.plone_major = int(self.plone_version[0])

    def pre(self, command, output_dir, vars):
        Package.pre(self, command, output_dir, vars)
        vars['plone_version'] = self.plone_version
        vars['major'] = self.plone_major
        self.load_plone_vars(command, output_dir, vars)
        if not 'with_ploneproduct_fss' in vars:
            vars['with_ploneproduct_fss'] = False


class P3Package(PlonePackage):
    themes = p3_themes
    vars = plone_vars + p3_vars


class P4Package(P3Package):
    themes = p4_themes
    paster_template = plone4.Template
    vars = plone_vars + p4_vars


class P41Package(P4Package):
    paster_template = plone41.Template
    vars = plone_vars + p41_vars


class P42Package(P41Package):
    paster_template = plone42.Template
    vars = plone_vars + p42_vars


class P43Package(P42Package):
    paster_template = plone43.Template
    vars = plone_vars + p43_vars

#class P44Package(P43Package):
#    paster_template = plone44.Template
#    vars = plone_vars + p44_vars
#
#class DjangoPackage(Package):
#    vars = Package.vars + django_vars
#
#    def __init__(self, *args, **kwargs):
#        Template.__init__(self, *args, **kwargs)
#
#    def pre(self, command, output_dir, vars):
#        Package.pre(self, command, output_dir, vars)
#        self.load_django_vars(command, output_dir, vars)
#
#    def load_django_vars(self, command, output_dir, vars):
#        vars['eggs_mappings'] = getattr(django.Template, 'eggs_mappings')
#
#class PyramidPackage(MinitagePackage):
#    vars = Package.vars + pyramid_vars
#    paster_template = pyramid.Template
#
