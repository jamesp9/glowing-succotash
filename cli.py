import argparse
import json

from pathlib import Path

import boto3
import boto3.session
import botocore

DEFAULT_CIDR = '10.0.0.0/16'
DEFAULT_NAME = 'demo'
services = ['vpc']


def write_output_json(filename, data):
    """Write JSON output to disk"""
    path = Path('outputs') / filename
    with open(path, 'w') as fo:
        json.dump(data, fo, indent=2)
    print(f'Written: {path}')


def read_output_json(filename):
    """"""
    path = Path('outputs') / filename
    with open(path, 'r') as fo:
        data = json.load(fo)
    return data


def main():
    """"""
    parser = argparse.ArgumentParser(
        description='Demo: Create AWS infrastructure with Python')
    parser.add_argument('--verbose', '-v', action='store_true', help='')
    parser.add_argument('--profile', action='store', default='demo',
                        help='AWS profile name, defaults to "demo"')
    parser.add_argument('--region', action='store', default='ap-southeast-2',
                        help='AWS region, defaults to "ap-southeast-2"')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debugging')

    subparsers = parser.add_subparsers(
        title='AWS Service',
        description='Select AWS service to work on',
        help='Choose the AWS service',
        metavar='service',
        dest='service'
    )
    # VPC options

    parser_vpc = subparsers.add_parser('vpc', help='Work on VPC')
    parser_vpc.add_argument('--action', choices=['create', 'info'],
                            action='store', required=True)
    parser_vpc.add_argument('--vpc_name', action='store', default='demo',
                            help='VPC Name tag')
    parser_vpc.set_defaults(func=vpc)

    # Subnet options

    parser_subnet = subparsers.add_parser('subnet', help='VPC subnets')
    parser_subnet.add_argument('--action', choices=['create', 'info'],
                               action='store', required=True)
    parser_subnet.add_argument('--name_prefix', action='store',
                               default=DEFAULT_NAME, help='Subnet name prefix')
    parser_subnet.set_defaults(func=subnet)

    # Internet Gateway options

    parser_igw = subparsers.add_parser('igw', help='Internet Gateway')
    parser_igw.add_argument('--action', choices=['create', 'info', 'attach'],
                            action='store', required=True)
    parser_igw.add_argument('--name', action='store',
                            default=DEFAULT_NAME,
                            help='Internet Gateway name')
    parser_igw.set_defaults(func=igw)

    # Route Table options

    parser_rt = subparsers.add_parser('route_table', help='Route Table')
    parser_rt.add_argument(
        '--action', action='store', required=True,
        choices=['create', 'info', 'associate_subnet', 'add_route']
    )
    parser_rt.add_argument('--name', action='store',
                           default=DEFAULT_NAME,
                           help='Prefix to route table name')
    parser_rt.set_defaults(func=rt)

    # EC2 options

    parser_ec2 = subparsers.add_parser('ec2', help='Elastic Compute Cloud')
    parser_ec2.add_argument(
        '--action', action='store', required=True,
        choices=['create', 'info', 'import_ssh_key']
    )
    parser_ec2.add_argument('--name', action='store', default=DEFAULT_NAME,
                            help='Name tag of EC2 instance')
    parser_ec2.set_defaults(func=ec2)

    # Security Group options

    parser_sg = subparsers.add_parser('security_group', help='Security Group')
    parser_sg.add_argument('--action', action='store', required=True,
                           choices=['create', 'info'])
    parser_sg.add_argument('--name', action='store', default=DEFAULT_NAME,
                           help='Security group name')
    parser_sg.set_defaults(func=security_group)

    # Handle arguments

    args = parser.parse_args()
    if not args.service:
        print(f'DEBUG: args: {args}\n')
        parser.print_usage()
        parser.exit(message='Select a service to work on.\n')

    args.func(args)


def vpc(args):
    """VPC"""
    if args.debug:
        print('VPC')
        print(f'args: {args}')

    session = boto3.session.Session(profile_name=args.profile,
                                    region_name=args.region)
    if args.action == 'info':
        vpcs = vpc_info(session, vpc_name=args.vpc_name)
        if vpcs:
            print(json.dumps(vpcs))

    elif args.action == 'create':
        vpcs = vpc_info(session, vpc_name=args.vpc_name)
        if not vpcs:
            vpc_create(session)
        else:
            print('VPC already exists')


def vpc_info(session, vpc_name=DEFAULT_NAME, cidr=DEFAULT_CIDR):
    """VPC Info"""
    client = session.client('ec2')
    response = client.describe_vpcs(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [vpc_name]
            },
            {
                'Name': 'cidr-block-association.cidr-block',
                'Values': [cidr]
            },
        ]
    )
    return response.get('Vpcs', None)


def vpc_create(session, cidr=DEFAULT_CIDR,
               tags=[{'Key': 'Name', 'Value': DEFAULT_NAME}]):
    """"""
    ec2_client = session.client('ec2')
    response = ec2_client.create_vpc(
        CidrBlock=cidr,
        InstanceTenancy='default',
        TagSpecifications=[
            {
                'ResourceType': 'vpc',
                'Tags': tags,
            },
        ]
    )

    vpc_id = response.get('Vpc', {}).get('VpcId')
    waiter = ec2_client.get_waiter('vpc_available')
    waiter.wait(
        VpcIds=[vpc_id],
    )
    print(f'VPC created: {vpc_id}')
    write_output_json('vpc.json', response)


def get_vpc_id():
    """"""
    vpc_json = Path.cwd() / 'outputs' / 'vpc.json'
    if not vpc_json.exists():
        return None

    with open(vpc_json, 'r') as fo:
        vpc_data = json.load(fo)
    return vpc_data.get('Vpc', {}).get('VpcId', None)


def get_availability_zones(session):
    """"""
    client = session.client('ec2')
    az_response = client.describe_availability_zones(Filters=[{
        'Name': 'group-name',
        'Values': ['ap-southeast-2']
    }])
    azs = []
    for az in az_response.get('AvailabilityZones', None):
        azs.append(az.get('ZoneName', None))
    return azs


def subnet(args):
    """"""
    if args.debug:
        print('Subnets')
        print(f'args: {args}')

    session = boto3.session.Session(profile_name=args.profile,
                                    region_name=args.region)
    if args.action == 'info':
        subnets = subnet_info(session, name_prefix=args.name_prefix)
        if subnets:
            print(json.dumps(subnets))
    elif args.action == 'create':
        subnets = subnet_info(session)
        if not subnets:
            subnet_create(session)
        else:
            print('Subnets already exist:',
                  [x.get('SubnetId', None) for x in subnets])


def subnet_info(session, name_prefix=DEFAULT_NAME):
    """"""
    client = session.client('ec2')
    response = client.describe_subnets(Filters=[
        {
            'Name': 'tag:Name',
            'Values': [
                'demo-ap-southeast-2a',
                'demo-ap-southeast-2b',
                'demo-ap-southeast-2c',
            ]
        },
        {'Name': 'vpc-id', 'Values': [get_vpc_id()]}
    ])
    return response.get('Subnets', None)


def subnet_create(session,
                  subnet_cidrs=['10.0.0.0/28', '10.0.0.16/28', '10.0.0.32/28']):
    """"""
    client = session.client('ec2')
    azs = get_availability_zones(session)
    print(f'AvailabilityZones: {azs}')

    responses = []
    for idx, az in enumerate(azs):
        response = client.create_subnet(
            TagSpecifications=[{'ResourceType': 'subnet',
                                'Tags': [{
                                    'Key': 'Name',
                                    'Value': f'demo-{az}'
                                }]}],
            AvailabilityZone=az,
            CidrBlock=subnet_cidrs[idx],
            VpcId=get_vpc_id(),
        )

        if response:
            responses.append(response)

    subnet_ids = []
    for response in responses:
        subnet_ids.append(response.get('Subnet', {}).get('SubnetId', None))

    waiter = client.get_waiter('subnet_available')
    waiter.wait(SubnetIds=subnet_ids)
    print(f'Subnets created: {subnet_ids}')

    write_output_json('subnets.json', responses)


def igw(args):
    """"""
    if args.debug:
        print('Internet Gateway')
        print(f'args: {args}')

    session = boto3.session.Session(profile_name=args.profile,
                                    region_name=args.region)
    if args.action == 'info':
        igws = igw_info(session, name=args.name)
        if igws:
            print(json.dumps(igws))
    elif args.action == 'create':
        igws = igw_info(session, name=args.name)
        if not igws:
            igw_create(session)
        else:
            print('Internet Gateway already exists')
    elif args.action == 'attach':
        igw_attach(session)


def igw_info(session, name=DEFAULT_NAME):
    """"""
    client = session.client('ec2')
    response = client.describe_internet_gateways(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [
                    name,
                ]
            },
        ],
    )
    return response.get('InternetGateways', None)


def igw_create(session, name=DEFAULT_NAME):
    """"""
    client = session.client('ec2')
    response = client.create_internet_gateway(
        TagSpecifications=[
            {
                'ResourceType': 'internet-gateway',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': f'{name}'
                    },
                ]
            },
        ],
    )
    # boto3 is missing a waiter for internetgateway
    igw_id = response.get('InternetGateway', {}).get('InternetGatewayId')
    print(f'InternetGateway created: {igw_id}')

    write_output_json('igw.json', response)


def igw_attach(session, igw_id=None, vpc_id=None):
    """Attach Internet Gateway to VPC"""
    client = session.client('ec2')

    with open('outputs/igw.json', 'r') as fo:
        data = json.load(fo)
    igw_id = data.get('InternetGateway', {}).get('InternetGatewayId', None)
    vpc_id = get_vpc_id()

    try:
        response = client.attach_internet_gateway(
            InternetGatewayId=igw_id,
            VpcId=vpc_id
        )
    except botocore.exceptions.ClientError as e:
        print(f'WARNING: Internet Gateway already attached: {e}')
        response = None

    print(f'Internet Gateway: {igw_id} attached to VPC: {vpc_id}')

    if response:
        write_output_json('igw_attach.json', response)


def rt(args):
    """Route Table"""
    if args.debug:
        print('Route Table')
        print(f'args: {args}')

    session = boto3.session.Session(profile_name=args.profile,
                                    region_name=args.region)
    if args.action == 'info':
        route_tables = rt_info(session, name=args.name)
        if route_tables:
            print(json.dumps(route_tables))
    elif args.action == 'create':
        route_tables = rt_info(session)
        if not route_tables:
            rt_create(session)
        else:
            print('Internet Gateway already exists')
    elif args.action == 'associate_subnet':
        rt_associate_with_subnet(session)
    elif args.action == 'add_route':
        route(session, dest_cidr='0.0.0.0/0')


def rt_info(session, name=DEFAULT_NAME):
    """"""
    client = session.client('ec2')
    response = client.describe_route_tables(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [
                    f'{name}-public',
                ]
            },
        ],
    )

    return response.get('RouteTables', None)


def rt_create(session, name=DEFAULT_NAME):
    """"""
    client = session.client('ec2')
    vpc_id = get_vpc_id()

    response = client.create_route_table(
        VpcId=vpc_id,
        TagSpecifications=[
            {
                'ResourceType': 'route-table',
                'Tags': [
                    {
                        'Key': 'tag:Name',
                        'Value': f'{name}-public'
                    },
                ]
            },
        ]
    )
    rt_id = response.get('RouteTable', {}).get('RouteTableId', None)
    print(f'Route table created: {rt_id}')

    write_output_json('route_table.json', response)


def rt_associate_with_subnet(session):
    """"""
    ec2 = session.resource('ec2')

    rt_data = read_output_json('route_table.json')
    rt_id = rt_data.get('RouteTable', {}).get('RouteTableId', None)
    route_table = ec2.RouteTable(rt_id)

    sn_data = read_output_json('subnets.json')
    sn_ids = [s.get('Subnet', {}).get('SubnetId', None) for s in sn_data]

    for sn_id in sn_ids:
        rt_association = route_table.associate_with_subnet(SubnetId=sn_id)
        print(f'Route Table association: {rt_association}')


def route(session, rt_id=None, dest_cidr=None):
    """"""
    client = session.client('ec2')

    igw_data = read_output_json('igw.json')
    igw_id = igw_data.get('InternetGateway', {}).get('InternetGatewayId', None)

    rt_data = read_output_json('route_table.json')
    rt_id = rt_data.get('RouteTable', {}).get('RouteTableId', None)

    response = client.create_route(DestinationCidrBlock=dest_cidr,
                                   GatewayId=igw_id,
                                   RouteTableId=rt_id)

    write_output_json('route.json', response)


def security_group(args):
    """Security Group"""
    if args.debug:
        print('Security Group')
        print(f'args: {args}')

    session = boto3.session.Session(profile_name=args.profile,
                                    region_name=args.region)

    if args.action == 'info':
        sec_groups = security_group_info(session, name=args.name)
        if sec_groups:
            print(json.dumps(sec_groups))
    elif args.action == 'create':
        sec_groups = security_group_info(session, name=args.name)
        if not sec_groups:
            security_group_create(session)
        else:
            print('Security Group already exists')


def security_group_info(session, name=DEFAULT_NAME):
    """"""


def security_group_create(session, name=DEFAULT_NAME):
    """"""
    client = session.client('ec2')
    try:
        response = client.create_security_group(
            Description=name,
            GroupName=name,
            VpcId=get_vpc_id(),
            TagSpecifications=[
                {
                    'ResourceType': 'security-group',
                    'Tags': [
                        {
                            'Key': 'tag:Name',
                            'Value': name
                        },
                    ]
                },
            ],
        )
    except botocore.exceptions.ClientError as e:
        print(f'ERROR: Security group already exists: {e}')
        return

    group_id = response.get('GroupId', None)

    waiter = client.get_waiter('security_group_exists')
    waiter.wait(
        GroupIds=[
            group_id,
        ],
    )

    print(f'Created security group: {group_id}')
    write_output_json('security_group.json', response)


def sg_ingress_rule(session, cidr=None):
    """"""
    sg_data = read_output_json('security_group.json')
    sg_id = sg_data.get('GroupId', None)

    ec2_resource = session.resource('ec2')
    sg = ec2_resource.SecurityGroup(sg_id)

    response = sg.authorize_ingress(
        CidrIp=cidr,
        FromPort=22,
        GroupName='demo-ssh',
        IpProtocol='tcp',
        ToPort=22,
    )


def ec2(args):
    """EC2"""
    if args.debug:
        print('EC2')
        print(f'args: {args}')

    session = boto3.session.Session(profile_name=args.profile,
                                    region_name=args.region)

    if args.action == 'info':
        ec2s = ec2_info(session, vpc_name=args.name)
        if ec2s:
            print(json.dumps(ec2s))
    elif args.action == 'create':
        ec2s = vpc_info(session, vpc_name=args.name)
        if not ec2s:
            ec2_create(session)
        else:
            print('VPC already exists')
    elif args.action == 'import_ssh_key':
        ec2_import_ssh_key(session)


def ec2_import_ssh_key(session, name=DEFAULT_NAME, keyname='aws-sydney-demo'):
    """"""
    pubkey_path = Path.home() / '.ssh' / f'{keyname}.pub'

    if pubkey_path.exists():
        with open(pubkey_path, 'rb') as fo:
            pubdata = fo.read()
    else:
        print(f'ERROR: {pubkey_path} does not exit. You may need to generate the key first.')
        print(f'ssh-keygen -f {pubkey_path} -N ""')
        return

    security_group

    client = session.client('ec2')
    try:
        response = client.import_key_pair(
            KeyName=keyname,
            PublicKeyMaterial=pubdata,
            TagSpecifications=[
                {
                    'ResourceType': 'key-pair',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': keyname
                        },
                    ]
                },
            ]
        )
        write_output_json('ssh_key_pair.json', response)
    except botocore.exceptions.ClientError as e:
        print(f'ERROR: Key import failed: {e}')


def ec2_info(session):
    """"""


def ec2_create(session, ami='ami-06ce513624b435a22', name=DEFAULT_NAME,
               instance_type='t3a.nano', ssh_key='aws-sydney-demo'):
    """"""
    ec2_client = session.client('ec2')
    ec2_resource = session.resource('ec2')

    instance = ec2_resource.create_instances(
        ImageId=ami,
        InstanceType=instance_type,
        KeyName=ssh_key,
        # SecurityGroupIds=[
        #     'string',
        # ],

        SubnetId='subnet-00f32a2732637f530',
        # NetworkInterfaces=[
        #     {
        #         'AssociatePublicIpAddress': True | False,
        #         'DeleteOnTermination': True | False,
        #         'Description': 'string',
        #         'DeviceIndex': 123,
        #         'Groups': [
        #             'string',
        #         ],
        #         'Ipv6AddressCount': 123,
        #         'Ipv6Addresses': [
        #             {
        #                 'Ipv6Address': 'string'
        #             },
        #         ],
        #         'NetworkInterfaceId': 'string',
        #         'PrivateIpAddress': 'string',
        #         'PrivateIpAddresses': [
        #             {
        #                 'Primary': True | False,
        #                 'PrivateIpAddress': 'string'
        #             },
        #         ],
        #         'SecondaryPrivateIpAddressCount': 123,
        #         'SubnetId': 'string',
        #         'AssociateCarrierIpAddress': True | False,
        #         'InterfaceType': 'string',
        #         'NetworkCardIndex': 123
        #     },
        # ],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': name
                    },
                ]
            },
        ],
    )

    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(
        Filters=[
            {
                'Name': 'instance-id',
                'Values': [
                    'string',
                ]
            },
        ],
        InstanceIds=[
            'string',
        ],
        DryRun=True | False,
        MaxResults=123,
        NextToken='string',
        WaiterConfig={
            'Delay': 123,
            'MaxAttempts': 123
        }
    )

    write_output_json('ec2_instance.json', instance)


if __name__ == '__main__':
    Path('outputs').mkdir(exist_ok=True)

    main()
