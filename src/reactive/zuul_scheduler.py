import os
import subprocess
import yaml

import charms.reactive as reactive
import charms.reactive.relations as relations

import charmhelpers.core as ch_core
import charmhelpers.core.templating as templating
import charmhelpers.core.hookenv as hookenv
# from charmhelpers.core.hookenv import log


@reactive.when('apt.installed.libre2-dev', 'apt.installed.python3-pip')
@reactive.when_not('zuul.installed')
def install_zuul():
    subprocess.check_call(['/usr/bin/pip3', 'install', 'zuul'])
    reactive.set_flag('zuul.installed')


@reactive.when('zuul.installed')
@reactive.when_not('endpoint.zookeeper.joined')
def connect_zookeeper():
    hookenv.status_set('blocked', 'Relate Zookeeper to continue')


@reactive.when('zuul.installed', 'endpoint.zookeeper.joined')
@reactive.when_not('endpoint.zookeeper.available')
def wait_for_zookeeper():
    hookenv.status_set('waiting', 'Waiting for Zookeeper to become available')


@reactive.when(
    'zuul.installed', 'endpoint.zookeeper.available')
@reactive.when_not('config.set.tenant-config')
def default_tenant_config():
    templating.render(
        'main.yaml', '/etc/zuul/main.yaml',
        context={}, perms=0o650, group='zuul', owner='zuul')
    reactive.clear_flag('zuul.configured')


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


@reactive.when_any('config.changed.connections')
def reset_configured():
    reactive.clear_flag('zuul.configured')


@reactive.when('zuul.installed',
               'endpoint.zookeeper.available',
               'zuul.user.created')
@reactive.when_not('zuul.configured')
def configure():
    zookeeper = relations.endpoint_from_flag('endpoint.zookeeper.available')
    connections = []
    try:
         connections = yaml.safe_load(hookenv.config().get('connections', []))
    except yaml.YAMLError:
        pass
    conf = {
        'zk_servers': [],
        'connections':
    }
    if hookenv.config()['tenant-config']:
        conf['tenant_config_script'] = True
    for zk_unit in zookeeper.list_unit_data():
        conf['zk_servers'].append(
            "{}:{}".format(zk_unit['host'].replace('"', ''), zk_unit['port']))
    templating.render(
        'zuul.conf', '/etc/zuul/zuul.conf',
        context=conf, perms=0o650, group='zuul', owner='zuul')
    reactive.set_flag('service.zuul.restart')
    reactive.set_flag('zuul.configured')


@reactive.when('service.zuul.restart')
def restart_services():
    ch_core.host.service_restart('zuul-scheduler')
    ch_core.host.service_restart('zuul-web')
    reactive.clear_flag('service.zuul.restart')


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


@reactive.when('zuul-scheduler.started',
               'zuul-web.started',
               'nginx.configured')
def set_ready():
    hookenv.status_set('active', 'Zuul is ready')
