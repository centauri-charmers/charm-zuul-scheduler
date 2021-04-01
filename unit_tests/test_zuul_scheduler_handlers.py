# Copyright 2018 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import print_function

import reactive.zuul_scheduler as handlers
import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        # hook_set = {
        #     'when': {
        #         'render_things': ('amqp.available',
        #                           'shared-db.available',),
        #     },
        # }
        defaults = []
        hook_set = {
            'when_not': {
                'configure': ('zuul.configured',),
                'wait_for_zookeeper': ('endpoint.zookeeper.available',),
                'install_zuul': ('zuul.installed',),
                'enable_scheduler': ('zuul-scheduler.started',),
                'enable_web': ('zuul-web.started',),
                'enable_executor': ('zuul-executor.started',),
                'connect_zookeeper': ('endpoint.zookeeper.joined',),
                'configure_tenant_config_script': (
                    'config.set.tenant-config',),
                'add_zuul_user': ('zuul.user.created',),
                'configure_nginx': ('nginx.configured',),
            },
            'when': {
                'install_zuul': (
                    'apt.installed.libre2-dev', 'apt.installed.python3-pip'),
                'configure_nginx': ('apt.installed.nginx',),
                'configure': (
                    'zuul.installed',
                    'endpoint.zookeeper.available',
                    'zuul.user.created'),
                'template_tenant_config': (
                    'zuul.user.created',
                    'zuul.installed',
                    'config.changed.zuul-config',),
                'configure_tenant_config_script': (
                    'zuul.installed', 'endpoint.zookeeper.available',
                    'config.set.tenant-config',),
                'wait_for_zookeeper': (
                    'zuul.installed', 'endpoint.zookeeper.joined',),
                'enable_scheduler': ('zuul.configured', 'zuul.user.created',),
                'enable_web': ('zuul.configured', 'zuul.user.created',),
                'enable_executor': ('zuul.configured', 'zuul.user.created',),
                'set_ready': (
                    'zuul-scheduler.started', 'zuul-web.started',
                    'zuul-executor.started', 'nginx.configured'),
                'connect_zookeeper': ('zuul.installed',),
                'configure_ssh_key': (
                    'zuul.user.created', 'config.set.ssh_key',),
                'restart_services': ('service.zuul.restart',),
                'reload_config': (
                    'zuul.reload_config', 'zuul-scheduler.started',),
            }
        }
        # test that the hooks were registered via the
        # reactive.zuul_scheduler handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)
