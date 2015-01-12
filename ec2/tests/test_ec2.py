########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

# Built-in Imports
import testtools

# Third Party Imports
from boto.ec2 import EC2Connection
from moto import mock_ec2

# Cloudify Imports is imported and used in operations
from ec2 import connection
from ec2 import instance
from ec2 import utils
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import NonRecoverableError

TEST_AMI_IMAGE_ID = 'ami-e214778a'
TEST_INSTANCE_TYPE = 't1.micro'


class TestPlugin(testtools.TestCase):

    def mock_ctx(self, test_name):

        test_node_id = test_name
        test_properties = {
            'image_id': TEST_AMI_IMAGE_ID,
            'instance_type': TEST_INSTANCE_TYPE,
            'attributes': {
                'security_groups': ['sg-73cd3f1e'],
                'instance_initiated_shutdown_behavior': 'stop'
            }
        }

        ctx = MockCloudifyContext(
            node_id=test_node_id,
            properties=test_properties
        )

        return ctx

    def test_instance_create(self):
        """ this tests that the instance create function works
        """

        ctx = self.mock_ctx('test_instance_create')

        with mock_ec2():
            instance.create(ctx=ctx)
            self.assertIn('instance_id',
                          ctx.instance.runtime_properties.keys())

    def test_instance_stop(self):
        """
        this tests that the instance stop function works
        """

        ctx = self.mock_ctx('test_instance_stop')

        with mock_ec2():
            ec2client = connection.EC2Client().ec2client()
            reservation = ec2client.run_instances(
                TEST_AMI_IMAGE_ID, instance_type=TEST_INSTANCE_TYPE)
            id = reservation.instances[0].id
            ctx.instance.runtime_properties['instance_id'] = id
            instance.stop(ctx=ctx)
            reservations = ec2client.get_all_reservations(id)
            instance_object = reservations[0].instances[0]
            state = instance_object.update()
            self.assertEqual(state, 'stopped')

    def test_instance_start(self):
        """ this tests that the instance.start function works
        """

        ctx = self.mock_ctx('test_instance_start')

        with mock_ec2():
            ec2client = connection.EC2Client().ec2client()
            reservation = ec2client.run_instances(
                TEST_AMI_IMAGE_ID, instance_type=TEST_INSTANCE_TYPE)
            id = reservation.instances[0].id
            ctx.instance.runtime_properties['instance_id'] = id
            ec2client.stop_instances(id)
            instance.start(ctx=ctx)
            reservations = ec2client.get_all_reservations(id)
            instance_object = reservations[0].instances[0]
            state = instance_object.update()
            self.assertEqual(state, 'running')

    def test_instance_terminate(self):
        """ this tests that the instance.terminate function
        works
        """

        ctx = self.mock_ctx('test_instance_terminate')

        with mock_ec2():
            ec2client = connection.EC2Client().ec2client()
            reservation = ec2client.run_instances(
                TEST_AMI_IMAGE_ID, instance_type=TEST_INSTANCE_TYPE)
            id = reservation.instances[0].id
            ctx.instance.runtime_properties['instance_id'] = id
            instance.terminate(ctx=ctx)
            reservations = ec2client.get_all_reservations(id)
            instance_object = reservations[0].instances[0]
            state = instance_object.update()
            self.assertEqual(state, 'terminated')

    @mock_ec2
    def test_connect(self):
        """ this tests that a the correct region endpoint
        in returned by the connect function
        """

        ec2client = connection.EC2Client().ec2client()
        self.assertTrue(type(ec2client), EC2Connection)
        self.assertEqual(ec2client.DefaultRegionEndpoint,
                         'ec2.us-east-1.amazonaws.com')

    def test_validate_instance_id(self):
        """ this tests that validate instance_id
        is true if provided with a valid instance_id
        """

        ctx = self.mock_ctx('test_validate_instance_id')

        with mock_ec2():
            ec2client = connection.EC2Client().ec2client()
            reservation = ec2client.run_instances(
                TEST_AMI_IMAGE_ID, instance_type=TEST_INSTANCE_TYPE)
            id = reservation.instances[0].id
            self.assertTrue(utils.validate_instance_id(id, ctx=ctx))

    def test_get_instance_state(self):
        """ this tests that get instance state returns
        running for a running instance
        """

        ctx = self.mock_ctx('test_get_instance_state')
        with mock_ec2():
            instance.create(ctx=ctx)
            instance_id = ctx.instance.runtime_properties['instance_id']
            instance_object = utils.get_instance_from_id(
                instance_id, ctx=ctx)
            instance_state = utils.get_instance_state(instance_object,
                                                      ctx=ctx)
            self.assertEqual(instance_state, 16)

    def test_bad_instance_id_start(self):
        """this tests that start fails when given an invalid
        instance_id
        """

        ctx = self.mock_ctx('test_bad_instance_id_start')

        with mock_ec2():
            ctx.instance.runtime_properties['instance_id'] = 'bad_id'
            ex = self.assertRaises(NonRecoverableError,
                                   instance.start, ctx=ctx)
            self.assertIn('InvalidInstanceID.NotFound', ex.message)

    def test_bad_instance_id_stop(self):
        """ this tests that stop fails when given an invalid
        instance_id
        """

        ctx = self.mock_ctx('test_bad_instance_id_stop')

        with mock_ec2():
            ctx.instance.runtime_properties['instance_id'] = 'bad_id'
            ex = self.assertRaises(NonRecoverableError,
                                   instance.stop, ctx=ctx)
            self.assertIn('InvalidInstanceID.NotFound', ex.message)

    def test_bad_instance_id_terminate(self):
        """ this tests that a terminate fails when given an
        invalid instance_id
        """

        ctx = self.mock_ctx('test_bad_instance_id_terminate')

        with mock_ec2():
            ctx.instance.runtime_properties['instance_id'] = 'bad_id'
            ex = self.assertRaises(NonRecoverableError,
                                   instance.terminate, ctx=ctx)
            self.assertIn('InvalidInstanceID.NotFound', ex.message)

    def test_timeout_validate_state(self):
        """ this tests that a stopped image is not in a 'pending' statement
        """

        ctx = self.mock_ctx('test_instance_running_validate_state')

        with mock_ec2():
            ec2client = connection.EC2Client().ec2client()
            shorter = TEST_INSTANCE_TYPE
            reservation = ec2client.run_instances(TEST_AMI_IMAGE_ID,
                                                  instance_type=shorter)
            id = reservation.instances[0].id
            ctx.instance.runtime_properties['instance_id'] = id
            instance_object = utils.get_instance_from_id(id, ctx=ctx)
            ec2client.stop_instances(id)
            ex = self.assertRaises(NonRecoverableError,
                                   utils.validate_state,
                                   instance_object, 0, 1, .1, ctx=ctx)
            self.assertIn('Timed out', ex.message)

    def test_no_instance_get_instance_from_id(self):
        """ this tests that a NonRecoverableError is thrown
        when a nonexisting instance_id is provided to the
        get_instance_from_id function
        """

        ctx = self.mock_ctx('test_no_instance_get_instance_from_id')

        with mock_ec2():

            id = 'bad_id'
            ex = self.assertRaises(NonRecoverableError,
                                   utils.get_instance_from_id, id, ctx=ctx)
            self.assertIn('InvalidInstanceID.NotFound', ex.message)

    def test_bad_subnet_id_create(self):
        """ This tests that the NonRecoverableError is triggered
        when an non existing subnet_id is included in the create
        statement
        """

        ctx = self.mock_ctx('test_bad_subnet_id_create')

        with mock_ec2():
            ctx.node.properties['attributes']['subnet_id'] = 'test'
            ex = self.assertRaises(NonRecoverableError,
                                   instance.create, ctx=ctx)
            self.assertIn('InvalidSubnetID.NotFound', ex.message)

    def test_bad_id_validate_instance_id(self):
        """ This tests that validate_id raises a NonRecoverableError
        when given an invalid id
        """

        ctx = self.mock_ctx('test_bad_id_validate_instance_id')

        with mock_ec2():
            ex = self.assertRaises(NonRecoverableError,
                                   utils.validate_instance_id,
                                   'bad id', ctx=ctx)
            self.assertIn('InvalidInstanceID.NotFound', ex.message)
