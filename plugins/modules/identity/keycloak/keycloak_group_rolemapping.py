#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2022, Marius Huysamen (@mhuysamen)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: keycloak_group_rolemapping

short_description: Allows administration of Keycloak group_rolemapping with the Keycloak API

version_added: 5.8.0

description:
    - This module allows you to add, remove or modify Keycloak group_rolemapping with the Keycloak REST API.
      It requires access to the REST API via OpenID Connect; the user connecting and the client being
      used must have the requisite access rights. In a default Keycloak installation, admin-cli
      and an admin user would work, as would a separate client definition with the scope tailored
      to your needs and a user having the expected roles.

    - The names of module options are snake_cased versions of the camelCase ones found in the
      Keycloak API and its documentation at U(https://www.keycloak.org/docs-api/18.0/rest-api/index.html).

    - Attributes are multi-valued in the Keycloak API. All attributes are lists of individual values and will
      be returned that way by this module. You may pass single values for attributes when calling the module,
      and this will be translated into a list suitable for the API.

    - When updating a group_rolemapping, where possible provide the role ID to the module. This removes a lookup
      to the API to translate the name into the role ID.


options:
    state:
        description:
            - State of the group_rolemapping.
            - On C(present), the group_rolemapping will be created if it does not yet exist, or updated with the parameters you provide.
            - On C(absent), the group_rolemapping will be removed if it exists.
        default: 'present'
        type: str
        choices:
            - present
            - absent

    realm:
        type: str
        description:
            - They Keycloak realm under which this role_representation resides.
        default: 'master'

    target_groupname:
        type: str
        description:
            - Name of the group roles are mapped to.
            - This parameter is not required (can be replaced by uid for less API call).

    gid:
        type: str
        description:
            - ID of the group to be mapped.
            - This parameter is not required for updating or deleting the rolemapping but
              providing it will reduce the number of API calls required.

    client_id:
        type: str
        description:
            - Name of the client to be mapped (different than I(cid)).
            - This parameter is required if I(cid) is not provided (can be replaced by I(cid)
              to reduce the number of API calls that must be made).

    cid:
        type: str
        description:
            - ID of the client to be mapped.
            - This parameter is not required for updating or deleting the rolemapping but
              providing it will reduce the number of API calls required.

    roles:
        description:
            - Roles to be mapped to the group.
        type: list
        elements: dict
        suboptions:
            name:
                type: str
                description:
                    - Name of the role representation.
                    - This parameter is required only when creating or updating the role_representation.
            id:
                type: str
                description:
                    - The unique identifier for this role_representation.
                    - This parameter is not required for updating or deleting a role_representation but
                      providing it will reduce the number of API calls required.

extends_documentation_fragment:
- community.general.keycloak


author:
    - Dušan Marković (@bratwurzt)
    - Marius Huysamen (@mhuysamen)
'''

EXAMPLES = '''
- name: Map a client role to a group, authentication with credentials
  community.general.keycloak_group_rolemapping:
    realm: MyCustomRealm
    auth_client_id: admin-cli
    auth_keycloak_url: https://auth.example.com/auth
    auth_realm: master
    auth_username: USERNAME
    auth_password: PASSWORD
    state: present
    client_id: client1
    group_id: group1Id
    roles:
      - name: role_name1
        id: role_id1
      - name: role_name2
        id: role_id2
  delegate_to: localhost

- name: Map a client role to a group, authentication with token
  community.general.keycloak_group_rolemapping:
    realm: MyCustomRealm
    auth_client_id: admin-cli
    auth_keycloak_url: https://auth.example.com/auth
    token: TOKEN
    state: present
    client_id: client1
    target_groupname: group1
    roles:
      - name: role_name1
        id: role_id1
      - name: role_name2
        id: role_id2
  delegate_to: localhost

- name: Unmap client role from a group
  community.general.keycloak_group_rolemapping:
    realm: MyCustomRealm
    auth_client_id: admin-cli
    auth_keycloak_url: https://auth.example.com/auth
    auth_realm: master
    auth_username: USERNAME
    auth_password: PASSWORD
    state: absent
    client_id: client1
    uid: 70e3ae72-96b6-11e6-9056-9737fd4d0764
    roles:
      - name: role_name1
        id: role_id1
      - name: role_name2
        id: role_id2
  delegate_to: localhost
'''

RETURN = '''
msg:
    description: Message as to what action was taken.
    returned: always
    type: str
    sample: "Role role1 assigned to group group1."

proposed:
    description: Representation of proposed client role mapping.
    returned: always
    type: dict
    sample: {
      clientId: "test"
    }

existing:
    description:
      - Representation of existing client role mapping.
      - The sample is truncated.
    returned: always
    type: dict
    sample: {
        "adminUrl": "http://www.example.com/admin_url",
        "attributes": {
            "request.object.signature.alg": "RS256",
        }
    }

end_state:
    description:
      - Representation of client role mapping after module execution.
      - The sample is truncated.
    returned: on success
    type: dict
    sample: {
        "adminUrl": "http://www.example.com/admin_url",
        "attributes": {
            "request.object.signature.alg": "RS256",
        }
    }
'''

from ansible_collections.community.general.plugins.module_utils.identity.keycloak.keycloak import KeycloakAPI, camel, \
    keycloak_argument_spec, get_token, KeycloakError, is_struct_included
from ansible.module_utils.basic import AnsibleModule


def main():
    """
    Module execution

    :return:
    """
    argument_spec = keycloak_argument_spec()

    roles_spec = dict(
        name=dict(type='str'),
        id=dict(type='str'),
    )

    meta_args = dict(
        state=dict(default='present', choices=['present', 'absent']),
        realm=dict(default='master'),
        gid=dict(type='str'),
        target_groupname=dict(type='str'),
        cid=dict(type='str'),
        client_id=dict(type='str'),
        roles=dict(type='list', elements='dict', options=roles_spec),
    )

    argument_spec.update(meta_args)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True,
                           required_one_of=([['token', 'auth_realm', 'auth_username', 'auth_password'],
                                             ['gid', 'target_groupname']]),
                           required_together=([['auth_realm', 'auth_username', 'auth_password']]))

    result = dict(changed=False, msg='', diff={}, proposed={}, existing={}, end_state={})

    # Obtain access token, initialize API
    try:
        connection_header = get_token(module.params)
    except KeycloakError as e:
        module.fail_json(msg=str(e))

    kc = KeycloakAPI(module, connection_header)

    realm = module.params.get('realm')
    state = module.params.get('state')
    cid = module.params.get('cid')
    client_id = module.params.get('client_id')
    gid = module.params.get('gid')
    target_groupname = module.params.get('target_groupname')
    roles = module.params.get('roles')

    # Check the parameters
    if gid is None and target_groupname is None:
        module.fail_json(msg='Either the `target_groupname` or `gid` has to be specified.')

    # Get the potential missing parameters
    if gid is None:
        group_rep = kc.get_group_by_name(name=target_groupname, realm=realm)
        if group_rep is not None:
            gid = group_rep.get('id')
        else:
            module.fail_json(msg='Could not fetch group for name %s:' % target_groupname)

    if cid is None and client_id is not None:
        cid = kc.get_client_id(client_id=client_id, realm=realm)
        if cid is None:
            module.fail_json(msg='Could not fetch client %s:' % client_id)

    if roles is None:
        module.exit_json(msg="Nothing to do (no roles specified).")
    else:
        for role_index, role in enumerate(roles, start=0):
            if role.get('name') is None and role.get('id') is None:
                module.fail_json(msg='Either the `name` or `id` has to be specified on each role.')
            # Fetch missing role_id
            if role.get('id') is None:
                if cid is None:
                    role_id = kc.get_realm_role(name=role.get('name'), realm=realm)['id']
                else:
                    role_id = kc.get_client_role_id_by_name(cid=cid, name=role.get('name'), realm=realm)
                if role_id is not None:
                    role['id'] = role_id
                else:
                    module.fail_json(msg='Could not fetch role %s for client_id %s or realm %s' % (role.get('name'), client_id, realm))
            # Fetch missing role_name
            else:
                if cid is None:
                    role['name'] = kc.get_realm_group_rolemapping_by_id(gid=gid, rid=role.get('id'), realm=realm)['name']
                else:
                    role['name'] = kc.get_client_group_rolemapping_by_id(gid=gid, cid=cid, rid=role.get('id'), realm=realm)['name']
                if role.get('name') is None:
                    module.fail_json(msg='Could not fetch role %s for client_id %s or realm %s' % (role.get('id'), client_id, realm))

    # Get effective role mappings
    if cid is None:
        available_roles_before = kc.get_realm_group_available_rolemappings(gid=gid, realm=realm)
        assigned_roles_before = kc.get_realm_group_composite_rolemappings(gid=gid, realm=realm)
    else:
        available_roles_before = kc.get_client_group_available_rolemappings(gid=gid, cid=cid, realm=realm)
        assigned_roles_before = kc.get_client_group_composite_rolemappings(gid=gid, cid=cid, realm=realm)

    result['existing'] = assigned_roles_before
    result['proposed'] = roles

    update_roles = []
    for role_index, role in enumerate(roles, start=0):
        # Fetch roles to assign if state present
        if state == 'present':
            for available_role in available_roles_before:
                if role.get('name') == available_role.get('name'):
                    update_roles.append({
                        'id': role.get('id'),
                        'name': role.get('name'),
                    })
        # Fetch roles to remove if state absent
        else:
            for assigned_role in assigned_roles_before:
                if role.get('name') == assigned_role.get('name'):
                    update_roles.append({
                        'id': role.get('id'),
                        'name': role.get('name'),
                    })

    if len(update_roles):
        if state == 'present':
            # Assign roles
            result['changed'] = True
            if module._diff:
                result['diff'] = dict(before=assigned_roles_before, after=update_roles)
            if module.check_mode:
                module.exit_json(**result)
            kc.add_group_rolemapping(gid=gid, cid=cid, role_rep=update_roles, realm=realm)
            result['msg'] = 'Roles %s assigned to groupId %s.' % (update_roles, gid)
            if cid is None:
                assigned_roles_after = kc.get_realm_group_composite_rolemappings(gid=gid, realm=realm)
            else:
                assigned_roles_after = kc.get_client_group_composite_rolemappings(gid=gid, cid=cid, realm=realm)
            result['end_state'] = assigned_roles_after
            module.exit_json(**result)
        else:
            # Remove mapping of role
            result['changed'] = True
            if module._diff:
                result['diff'] = dict(before=assigned_roles_before, after=update_roles)
            if module.check_mode:
                module.exit_json(**result)
            kc.delete_group_rolemapping(uid=gid, cid=cid, role_rep=update_roles, realm=realm)
            result['msg'] = 'Roles %s removed from groupId %s.' % (update_roles, gid)
            if cid is None:
                assigned_roles_after = kc.get_realm_group_composite_rolemappings(gid=gid, realm=realm)
            else:
                assigned_roles_after = kc.get_client_group_composite_rolemappings(gid=gid, cid=cid, realm=realm)
            result['end_state'] = assigned_roles_after
            module.exit_json(**result)
    # Do nothing
    else:
        result['changed'] = False
        result['msg'] = 'Nothing to do, roles %s are correctly mapped to group %s.' % (roles, target_groupname)
        module.exit_json(**result)


if __name__ == '__main__':
    main()
