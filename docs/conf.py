# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys

sys.path.insert(0, os.path.abspath(".."))


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
    "sphinx.ext.todo",
    "sphinx.ext.mathjax",
    "sphinx.ext.ifconfig",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx.ext.graphviz",
    "sphinx.ext.imgmath",
    "sphinx.ext.doctest",
    "sphinx.ext.napoleon",
]
source_suffix = ".rst"
master_doc = "index"
project = "PSCAD_import_tool_for_IEC_61400-27_DLLs"
year = "2026"
author = "Gregor Becker, Dominik Frauenknecht"
version = release = "0.0.1"

pygments_style = "trac"
templates_path = ["."]

# on_rtd is whether we are on readthedocs.org
on_rtd = os.environ.get("READTHEDOCS", None) == "True"

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']
html_use_smartypants = True
html_last_updated_fmt = "%b %d, %Y"
html_split_index = False
html_sidebars = {
    "**": ["searchbox.html", "globaltoc.html", "sourcelink.html"],
}
html_short_title = "%s-%s" % (project, version)

napoleon_use_ivar = True
napoleon_use_rtype = False
napoleon_use_param = False

def setup(app):
    app.add_css_file('custom.css')  # Sphinx >= 1.8

from docutils.parsers.rst import roles
from docutils.nodes import superscript

def sup_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    node = superscript(text, text)
    return [node], []

roles.register_local_role('sup', sup_role)
