# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
:mod:`cinder.tests.unit` -- Cinder Unittests
=====================================================

.. automodule:: cinder.tests.unit
   :platform: Unix
.. moduleauthor:: Jesse Andrews <jesse@ansolabs.com>
.. moduleauthor:: Devin Carlen <devin.carlen@gmail.com>
.. moduleauthor:: Vishvananda Ishaya <vishvananda@gmail.com>
.. moduleauthor:: Joshua McKenty <joshua@cognition.ca>
.. moduleauthor:: Manish Singh <yosh@gimp.org>
.. moduleauthor:: Andy Smith <andy@anarkystic.com>
"""

import eventlet
from six.moves import builtins

from cinder import objects

eventlet.monkey_patch()

# See http://code.google.com/p/python-nose/issues/detail?id=373
# The code below enables nosetests to work with i18n _() blocks
setattr(builtins, '_', lambda x: x)

# NOTE(alaski): Make sure this is done after eventlet monkey patching otherwise
# the threading.local() store used in oslo_messaging will be initialized to
# threadlocal storage rather than greenthread local.  This will cause context
# sets and deletes in that storage to clobber each other.
# NOTE(comstud): Make sure we have all of the objects loaded. We do this
# at module import time, because we may be using mock decorators in our
# tests that run at import time.
objects.register_all()
