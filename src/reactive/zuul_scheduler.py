import base64
import os
import subprocess
import yaml

import charms.reactive as reactive
# import reactive.helpers
import charms.reactive.relations as relations

import charmhelpers.core as ch_core
import charmhelpers.core.host as ch_host
import charmhelpers.core.templating as templating
import charmhelpers.core.hookenv as hookenv
# from charmhelpers.core.hookenv import log


@reactive.when('apt.installed.libre2-dev', 'apt.installed.python3-pip')
@reactive.when_not('zuul.installed')
def install_zuul():
    subprocess.check_call(['/usr/bin/pip3', 'install', 'zuul<4'])
    reactive.set_flag('zuul.installed')


@reactive.when('zuul.installed')
@reactive.when_not('endpoint.zookeeper.joined')
def connect_zookeeper():
    hookenv.status_set('blocked', 'Relate Zookeeper to continue')


@reactive.when('zuul.installed', 'endpoint.zookeeper.joined')
@reactive.when_not('endpoint.zookeeper.available')
def wait_for_zookeeper():
    hookenv.status_set('waiting', 'Waiting for Zookeeper to become available')


@reactive.when('endpoint.zookeeper.available')
@reactive.when_not('shared-db.connected')
def wait_for_db():
    hookenv.status_set('blocked', 'Relate database to continue')


@reactive.when('shared-db.connected')
@reactive.when_not('shared-db.available')
def setup_database(database):
    database.configure('zuul', 'zuul')
    hookenv.status_set('waiting', 'Waiting for database to become available')


@reactive.when(
    'zuul.user.created',
    'zuul.installed',
    'config.changed.zuul-config')
def template_tenant_config():
    conf = {
        'config': hookenv.config().get('zuul-config')
    }
    templating.render(
        'main.yaml', '/etc/zuul/main.yaml',
        context=conf, perms=0o650, group='zuul', owner='zuul')
    if reactive.helpers.any_file_changed(['/etc/zuul/main.yaml']):
        reactive.set_flag('zuul.reload_config')


@reactive.when(
    'zuul.installed', 'endpoint.zookeeper.available')
@reactive.when('config.set.tenant-config')
def configure_tenant_config_script():
    conf = {
        'tenant_config_script': hookenv.config()['tenant-config']
    }
    templating.render(
        'tenant_config_script.sh', '/etc/zuul/tenant_config.sh',
        context=conf, perms=0o755, group='zuul', owner='zuul')
    reactive.clear_flag('zuul.configured')


@reactive.when('apt.installed.nginx')
@reactive.when_not('nginx.configured')
def configure_nginx():
    templating.render(
        'zuul-web.conf', '/etc/nginx/sites-enabled/zuul-ci.conf',
        context={}, perms=0o650)
    os.remove('/etc/nginx/sites-enabled/default')
    ch_core.host.service_restart('nginx')
    reactive.set_flag('nginx.configured')


@reactive.when_any('config.changed.connections',
                   'endpoint.zookeeper.changed',)
def reset_configured():
    reactive.clear_flag('zuul.configured')


@reactive.when('zuul.user.created',
               'config.set.ssh_key',)
def configure_ssh_key():
    key = base64.b64decode(hookenv.config().get('ssh_key', ''))
    ch_host.mkdir('/var/lib/zuul/.ssh/', owner='zuul',
                  group='zuul', perms=0o700)
    ch_host.write_file('/var/lib/zuul/.ssh/id_rsa', content=key, owner='zuul',
                       group='zuul', perms=0o600)


@reactive.when('zuul.installed',
               'endpoint.zookeeper.available',
               'shared-db.available',
               'zuul.user.created')
@reactive.when_not('zuul.configured')
def configure():
    zookeeper = relations.endpoint_from_flag('endpoint.zookeeper.available')
    connections = []
    try:
        connections_yaml = hookenv.config().get('connections')
        if connections_yaml:
            connections = yaml.safe_load(connections_yaml)
    except yaml.YAMLError:
        pass
    mysql = relations.endpoint_from_flag('shared-db.available')
    conf = {
        'zk_servers': [],
        'connections': connections,
        'database': mysql,
        'git_username': hookenv.config().get('git_username'),
        'git_email': hookenv.config().get('git_email'),
        'executor_disk_limit': hookenv.config().get(
            'executor_disk_limit', '-1'),
        'public_ip': hookenv.unit_public_ip(),
    }
    if hookenv.config()['tenant-config']:
        conf['tenant_config_script'] = True
    for zk_unit in zookeeper.list_unit_data():
        conf['zk_servers'].append(
            "{}:{}".format(zk_unit['host'].replace('"', ''), zk_unit['port']))
    templating.render(
        'zuul.conf', '/etc/zuul/zuul.conf',
        context=conf, perms=0o650, group='zuul', owner='zuul')
    if reactive.helpers.any_file_changed(['/etc/zuul/zuul.conf']):
        reactive.set_flag('service.zuul.restart')
        reactive.set_flag('zuul.reload_config')
        reactive.set_flag('zuul.configured')


@reactive.when('service.zuul.restart')
def restart_services():
    ch_core.host.service_restart('zuul-executor')
    ch_core.host.service_restart('zuul-web')
    reactive.clear_flag('service.zuul.restart')


@reactive.when('zuul.reload_config',
               'zuul-scheduler.started')
def reload_config():
    # we don't want to restart the zuul-scheduler process unless absolutely
    # necessary. That means that we want to "resume" (enable and start) the
    # scheduler process and then call it's full-reconfigure call. This
    # ensures that the process is running and that it's configuration has
    # been reloaded.
    try:
        subprocess.check_call(['zuul-scheduler', 'full-reconfigure'])
    except subprocess.CalledProcessError:
        ch_core.host.service_restart('zuul-scheduler')


@reactive.when_not('zuul.user.created')
def add_zuul_user():
    subprocess.check_call(["groupadd", "--system", "zuul"])
    subprocess.check_call([
        'useradd', '--system', 'zuul',
        '--home-dir', '/var/lib/zuul', '--create-home',
        '-g', 'zuul'])
    reactive.set_flag('zuul.user.created')


@reactive.when('zuul.configured', 'zuul.user.created')
@reactive.when_not('zuul-scheduler.started')
def enable_scheduler():
    templating.render(
        'zuul-scheduler.service', '/etc/systemd/system/zuul-scheduler.service',
        context={})
    ch_core.host.service_resume('zuul-scheduler')
    reactive.set_flag('zuul-scheduler.started')


@reactive.when('zuul.configured', 'zuul.user.created')
@reactive.when_not('zuul-web.started')
def enable_web():
    templating.render(
        'zuul-web.service', '/etc/systemd/system/zuul-web.service',
        context={})
    ch_core.host.service_resume('zuul-web')
    reactive.set_flag('zuul-web.started')
    hookenv.open_port(80)


@reactive.when('zuul.configured', 'zuul.user.created')
@reactive.when_not('zuul-executor.started')
def enable_executor():
    templating.render(
        'zuul-executor.service', '/etc/systemd/system/zuul-executor.service',
        context={})
    ch_core.host.service_resume('zuul-executor')
    reactive.set_flag('zuul-executor.started')


@reactive.when('zuul-scheduler.started',
               'zuul-web.started',
               'zuul-executor.started',
               'nginx.configured')
def set_ready():
    hookenv.status_set('active', 'Zuul is ready')


@reactive.when('endpoint.prometheus.available',
               'snap.installed.icey-prometheus-statsd-exporter')
def setup_prometheus():
    prometheus = relations.endpoint_from_flag('endpoint.prometheus.available')
    prometheus.configure(port=9102)
