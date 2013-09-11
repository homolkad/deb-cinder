# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright (c) 2013 The Johns Hopkins University/Applied Physics Laboratory
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
A mock implementation of a key manager. This module should NOT be used for
anything but integration testing.
"""

import array

from cinder import exception
from cinder.keymgr import key
from cinder.keymgr import key_mgr
from cinder.openstack.common import log as logging
from cinder.openstack.common import uuidutils
from cinder import utils


LOG = logging.getLogger(__name__)


class MockKeyManager(key_mgr.KeyManager):

    """
    This mock key manager implementation supports all the methods specified
    by the key manager interface. This implementation stores keys within a
    dictionary, and as a result, it is not acceptable for use across different
    services. Side effects (e.g., raising exceptions) for each method are
    handled as specified by the key manager interface.

    This class should NOT be used for anything but integration testing because
    keys are not stored persistently.
    """

    def __init__(self):
        self.keys = {}

    def create_key(self, ctxt, **kwargs):
        """Creates a key.

        This implementation returns a UUID for the created key. A
        NotAuthorized exception is raised if the specified context is None.
        """
        if ctxt is None:
            raise exception.NotAuthorized()

        # generate the key
        key_length = kwargs.get('key_length', 256)
        # hex digit => 4 bits
        hex_string = utils.generate_password(length=key_length / 4,
                                             symbolgroups='0123456789ABCDEF')

        _bytes = array.array('B', hex_string.decode('hex')).tolist()
        _key = key.SymmetricKey('AES', _bytes)

        return self.store_key(ctxt, _key)

    def _generate_key_id(self):
        key_id = uuidutils.generate_uuid()
        while key_id in self.keys:
            key_id = uuidutils.generate_uuid()

        return key_id

    def store_key(self, ctxt, key, **kwargs):
        """Stores (i.e., registers) a key with the key manager.
        """
        if ctxt is None:
            raise exception.NotAuthorized()

        key_id = self._generate_key_id()
        self.keys[key_id] = key

        return key_id

    def copy_key(self, ctxt, key_id, **kwargs):
        if ctxt is None:
            raise exception.NotAuthorized()

        copied_key_id = self._generate_key_id()
        self.keys[copied_key_id] = self.keys[key_id]

        return copied_key_id

    def get_key(self, ctxt, key_id, **kwargs):
        """Retrieves the key identified by the specified id.

        This implementation returns the key that is associated with the
        specified UUID. A NotAuthorized exception is raised if the specified
        context is None; a KeyError is raised if the UUID is invalid.
        """
        if ctxt is None:
            raise exception.NotAuthorized()

        return self.keys[key_id]

    def delete_key(self, ctxt, key_id, **kwargs):
        """Deletes the key identified by the specified id.

        A NotAuthorized exception is raised if the context is None and a
        KeyError is raised if the UUID is invalid.
        """
        if ctxt is None:
            raise exception.NotAuthorized()

        del self.keys[key_id]
