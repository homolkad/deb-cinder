#    Copyright 2015 SimpliVity Corp.
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

import mock

from cinder import context
from cinder import exception
from cinder import objects
from cinder.tests.unit import fake_consistencygroup
from cinder.tests.unit import fake_snapshot
from cinder.tests.unit import fake_volume
from cinder.tests.unit import objects as test_objects


class TestVolume(test_objects.BaseObjectsTestCase):
    @staticmethod
    def _compare(test, db, obj):
        db = {k: v for k, v in db.items()
              if not k.endswith('metadata') or k.startswith('volume')}
        test_objects.BaseObjectsTestCase._compare(test, db, obj)

    @mock.patch('cinder.db.sqlalchemy.api.volume_get')
    def test_get_by_id(self, volume_get):
        db_volume = fake_volume.fake_db_volume()
        volume_get.return_value = db_volume
        volume = objects.Volume.get_by_id(self.context, 1)
        self._compare(self, db_volume, volume)
        volume_get.assert_called_once_with(self.context, 1)

    @mock.patch('cinder.db.sqlalchemy.api.model_query')
    def test_get_by_id_no_existing_id(self, model_query):
        pf = model_query().options().options().options().options().options()
        pf.filter_by().first.return_value = None
        self.assertRaises(exception.VolumeNotFound,
                          objects.Volume.get_by_id, self.context, 123)

    @mock.patch('cinder.db.volume_create')
    def test_create(self, volume_create):
        db_volume = fake_volume.fake_db_volume()
        volume_create.return_value = db_volume
        volume = objects.Volume(context=self.context)
        volume.create()
        self.assertEqual(db_volume['id'], volume.id)

    @mock.patch('cinder.db.volume_update')
    def test_save(self, volume_update):
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.display_name = 'foobar'
        volume.save()
        volume_update.assert_called_once_with(self.context, volume.id,
                                              {'display_name': 'foobar'})

    @mock.patch('cinder.db.volume_metadata_update',
                return_value={'key1': 'value1'})
    @mock.patch('cinder.db.volume_update')
    def test_save_with_metadata(self, volume_update, metadata_update):
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.display_name = 'foobar'
        volume.metadata = {'key1': 'value1'}
        self.assertEqual({'display_name': 'foobar',
                          'metadata': {'key1': 'value1'}},
                         volume.obj_get_changes())
        volume.save()
        volume_update.assert_called_once_with(self.context, volume.id,
                                              {'display_name': 'foobar'})
        metadata_update.assert_called_once_with(self.context, volume.id,
                                                {'key1': 'value1'}, True)

    @mock.patch('cinder.db.volume_admin_metadata_update',
                return_value={'key1': 'value1'})
    @mock.patch('cinder.db.volume_update')
    def test_save_with_admin_metadata(self, volume_update,
                                      admin_metadata_update):
        # Test with no admin context
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.admin_metadata = {'key1': 'value1'}
        volume.save()
        self.assertFalse(admin_metadata_update.called)

        # Test with admin context
        admin_context = context.RequestContext(self.user_id, self.project_id,
                                               is_admin=True)
        volume = objects.Volume._from_db_object(admin_context,
                                                objects.Volume(), db_volume)
        volume.admin_metadata = {'key1': 'value1'}
        volume.save()
        admin_metadata_update.assert_called_once_with(
            admin_context, volume.id, {'key1': 'value1'}, True)

    def test_save_with_glance_metadata(self):
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.display_name = 'foobar'
        volume.glance_metadata = {'key1': 'value1'}
        self.assertRaises(exception.ObjectActionError, volume.save)

    def test_save_with_consistencygroup(self):
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.display_name = 'foobar'
        volume.consistencygroup = objects.ConsistencyGroup()
        self.assertRaises(exception.ObjectActionError, volume.save)

    def test_save_with_snapshots(self):
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.display_name = 'foobar'
        volume.snapshots = objects.SnapshotList()
        self.assertRaises(exception.ObjectActionError, volume.save)

    @mock.patch('cinder.db.volume_destroy')
    def test_destroy(self, volume_destroy):
        db_volume = fake_volume.fake_db_volume()
        volume = objects.Volume._from_db_object(self.context,
                                                objects.Volume(), db_volume)
        volume.destroy()
        self.assertTrue(volume_destroy.called)
        admin_context = volume_destroy.call_args[0][0]
        self.assertTrue(admin_context.is_admin)

    def test_obj_fields(self):
        volume = objects.Volume(context=self.context, id=2, _name_id=2)
        self.assertEqual(['name', 'name_id'], volume.obj_extra_fields)
        self.assertEqual('volume-2', volume.name)
        self.assertEqual('2', volume.name_id)

    def test_obj_field_previous_status(self):
        volume = objects.Volume(context=self.context,
                                previous_status='backing-up')
        self.assertEqual('backing-up', volume.previous_status)

    @mock.patch('cinder.db.volume_metadata_delete')
    def test_delete_metadata_key(self, metadata_delete):
        volume = objects.Volume(self.context, id=1)
        volume.metadata = {'key1': 'value1', 'key2': 'value2'}
        self.assertEqual({}, volume._orig_metadata)
        volume.delete_metadata_key('key2')
        self.assertEqual({'key1': 'value1'}, volume.metadata)
        metadata_delete.assert_called_once_with(self.context, '1', 'key2')

    @mock.patch('cinder.db.volume_metadata_get')
    @mock.patch('cinder.db.volume_glance_metadata_get')
    @mock.patch('cinder.db.volume_admin_metadata_get')
    @mock.patch('cinder.objects.volume_type.VolumeType.get_by_id')
    @mock.patch('cinder.objects.volume_attachment.VolumeAttachmentList.'
                'get_all_by_volume_id')
    @mock.patch('cinder.objects.consistencygroup.ConsistencyGroup.get_by_id')
    @mock.patch('cinder.objects.snapshot.SnapshotList.get_all_for_volume')
    def test_obj_load_attr(self, mock_sl_get_all_for_volume, mock_cg_get_by_id,
                           mock_va_get_all_by_vol, mock_vt_get_by_id,
                           mock_admin_metadata_get, mock_glance_metadata_get,
                           mock_metadata_get):
        volume = objects.Volume._from_db_object(
            self.context, objects.Volume(), fake_volume.fake_db_volume())

        # Test metadata lazy-loaded field
        metadata = {'foo': 'bar'}
        mock_metadata_get.return_value = metadata
        self.assertEqual(metadata, volume.metadata)
        mock_metadata_get.assert_called_once_with(self.context, volume.id)

        # Test glance_metadata lazy-loaded field
        glance_metadata = {'foo': 'bar'}
        mock_glance_metadata_get.return_value = glance_metadata
        self.assertEqual(glance_metadata, volume.glance_metadata)
        mock_glance_metadata_get.assert_called_once_with(
            self.context, volume.id)

        # Test volume_type lazy-loaded field
        volume_type = objects.VolumeType(context=self.context, id=5)
        mock_vt_get_by_id.return_value = volume_type
        self.assertEqual(volume_type, volume.volume_type)
        mock_vt_get_by_id.assert_called_once_with(self.context,
                                                  volume.volume_type_id)

        # Test consistencygroup lazy-loaded field
        consistencygroup = objects.ConsistencyGroup(context=self.context, id=2)
        mock_cg_get_by_id.return_value = consistencygroup
        self.assertEqual(consistencygroup, volume.consistencygroup)
        mock_cg_get_by_id.assert_called_once_with(self.context,
                                                  volume.consistencygroup_id)

        # Test snapshots lazy-loaded field
        snapshots = objects.SnapshotList(context=self.context, id=2)
        mock_sl_get_all_for_volume.return_value = snapshots
        self.assertEqual(snapshots, volume.snapshots)
        mock_sl_get_all_for_volume.assert_called_once_with(self.context,
                                                           volume.id)

        # Test volume_attachment lazy-loaded field
        va_objs = [objects.VolumeAttachment(context=self.context, id=i)
                   for i in [3, 4, 5]]
        va_list = objects.VolumeAttachmentList(context=self.context,
                                               objects=va_objs)
        mock_va_get_all_by_vol.return_value = va_list
        self.assertEqual(va_list, volume.volume_attachment)
        mock_va_get_all_by_vol.assert_called_once_with(self.context, volume.id)

        # Test admin_metadata lazy-loaded field - user context
        adm_metadata = {'bar': 'foo'}
        mock_admin_metadata_get.return_value = adm_metadata
        self.assertEqual({}, volume.admin_metadata)
        self.assertFalse(mock_admin_metadata_get.called)

        # Test admin_metadata lazy-loaded field - admin context
        adm_context = self.context.elevated()
        volume = objects.Volume._from_db_object(adm_context, objects.Volume(),
                                                fake_volume.fake_db_volume())
        adm_metadata = {'bar': 'foo'}
        mock_admin_metadata_get.return_value = adm_metadata
        self.assertEqual(adm_metadata, volume.admin_metadata)
        mock_admin_metadata_get.assert_called_once_with(adm_context, volume.id)

    def test_from_db_object_with_all_expected_attributes(self):
        expected_attrs = ['metadata', 'admin_metadata', 'glance_metadata',
                          'volume_type', 'volume_attachment',
                          'consistencygroup']

        db_metadata = [{'key': 'foo', 'value': 'bar'}]
        db_admin_metadata = [{'key': 'admin_foo', 'value': 'admin_bar'}]
        db_glance_metadata = [{'key': 'glance_foo', 'value': 'glance_bar'}]
        db_volume_type = fake_volume.fake_db_volume_type()
        db_volume_attachments = fake_volume.fake_db_volume_attachment()
        db_consistencygroup = fake_consistencygroup.fake_db_consistencygroup()
        db_snapshots = fake_snapshot.fake_db_snapshot()

        db_volume = fake_volume.fake_db_volume(
            volume_metadata=db_metadata,
            volume_admin_metadata=db_admin_metadata,
            volume_glance_metadata=db_glance_metadata,
            volume_type=db_volume_type,
            volume_attachment=[db_volume_attachments],
            consistencygroup=db_consistencygroup,
            snapshots=[db_snapshots],
        )
        volume = objects.Volume._from_db_object(self.context, objects.Volume(),
                                                db_volume, expected_attrs)

        self.assertEqual({'foo': 'bar'}, volume.metadata)
        self.assertEqual({'admin_foo': 'admin_bar'}, volume.admin_metadata)
        self.assertEqual({'glance_foo': 'glance_bar'}, volume.glance_metadata)
        self._compare(self, db_volume_type, volume.volume_type)
        self._compare(self, db_volume_attachments, volume.volume_attachment)
        self._compare(self, db_consistencygroup, volume.consistencygroup)
        self._compare(self, db_snapshots, volume.snapshots)


class TestVolumeList(test_objects.BaseObjectsTestCase):
    @mock.patch('cinder.db.volume_get_all')
    def test_get_all(self, volume_get_all):
        db_volume = fake_volume.fake_db_volume()
        volume_get_all.return_value = [db_volume]

        volumes = objects.VolumeList.get_all(self.context,
                                             mock.sentinel.marker,
                                             mock.sentinel.limit,
                                             mock.sentinel.sort_key,
                                             mock.sentinel.sort_dir)
        self.assertEqual(1, len(volumes))
        TestVolume._compare(self, db_volume, volumes[0])

    @mock.patch('cinder.db.volume_get_all_by_host')
    def test_get_by_host(self, get_all_by_host):
        db_volume = fake_volume.fake_db_volume()
        get_all_by_host.return_value = [db_volume]

        volumes = objects.VolumeList.get_all_by_host(
            self.context, 'fake-host')
        self.assertEqual(1, len(volumes))
        TestVolume._compare(self, db_volume, volumes[0])

    @mock.patch('cinder.db.volume_get_all_by_group')
    def test_get_by_group(self, get_all_by_group):
        db_volume = fake_volume.fake_db_volume()
        get_all_by_group.return_value = [db_volume]

        volumes = objects.VolumeList.get_all_by_group(
            self.context, 'fake-host')
        self.assertEqual(1, len(volumes))
        TestVolume._compare(self, db_volume, volumes[0])

    @mock.patch('cinder.db.volume_get_all_by_project')
    def test_get_by_project(self, get_all_by_project):
        db_volume = fake_volume.fake_db_volume()
        get_all_by_project.return_value = [db_volume]

        volumes = objects.VolumeList.get_all_by_project(
            self.context, mock.sentinel.project_id, mock.sentinel.marker,
            mock.sentinel.limit, mock.sentinel.sorted_keys,
            mock.sentinel.sorted_dirs, mock.sentinel.filters)
        self.assertEqual(1, len(volumes))
        TestVolume._compare(self, db_volume, volumes[0])
