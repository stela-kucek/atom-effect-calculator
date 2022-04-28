#!/home/ubuntu/gridsolver-app/.env/bin/python3
import multiprocessing as mp
import boto3
import json
import numpy as np

sqs = boto3.client('sqs')
sns = boto3.client('sns')

queue_url = 'https://sqs.us-east-1.amazonaws.com/283893968322/queue2.fifo'


def calculate_effect_on_grid_point(point_x: float, point_y: float, point_z: float, atoms: [], arn: str) -> float:
    total_effect = 0.0
    for atom in atoms:
        d = abs(atom['x'] - point_x) + abs(atom['y'] - point_y) + abs(atom['z'] - point_z)
        total_effect += atom['e'] / d
        send_update_to_gui(arn, 'Atom processed')
    return round(total_effect, 4)


def ndmesh(*xi):
    if len(xi) < 2:
        msg = 'meshgrid() takes 2 or more arguments (%d given)' % int(len(xi) > 0)
        raise ValueError(msg)

    args = np.atleast_1d(*xi)
    ndim = len(args)

    s0 = (1,) * ndim
    output = [x.reshape(s0[:i] + (-1,) + s0[i + 1::]) for i, x in enumerate(args)]

    return np.broadcast_arrays(*output)


def get_atom_x_array(atoms):
    arr = []
    for a in atoms:
        arr.append(a['x'])
    return arr


def get_atom_y_array(atoms):
    arr = []
    for a in atoms:
        arr.append(a['y'])
    return arr


def get_atom_z_array(atoms):
    arr = []
    for a in atoms:
        arr.append(a['z'])
    return arr


def get_atom_e_array(atoms):
    arr = []
    for a in atoms:
        arr.append(a['e'])
    return arr


def calculate_parallel(points, atom_values, arn, return_dict=None):
    effects = np.array([], dtype=float)
    a_xs = np.array(get_atom_x_array(atom_values), dtype=float)
    a_ys = np.array(get_atom_y_array(atom_values), dtype=float)
    a_zs = np.array(get_atom_z_array(atom_values), dtype=float)
    a_es = np.array(get_atom_e_array(atom_values), dtype=float)
    for p in points:
        # print('processed')
        d_x = np.abs(a_xs - p[0])
        d_y = np.abs(a_ys - p[1])
        d_z = np.abs(a_zs - p[2])

        ds = d_x + d_y + d_z
        effect = np.round(a_es / ds, 4)
        effects = np.append(effects, np.sum(effect))
        print('TOPIC ARN %s' % arn)
        msg = 'Grid point ' + str(p) + ' processed, ' + arn
        send_update_to_gui(arn, msg)
    print(effects)
    minimum = round(min(effects), 4)
    point_min = str(points[effects.argmin()])
    if return_dict is not None:
        return_dict[point_min] = minimum
    else:
        # print('min effect parallel: %s' % minimum)
        # print('at point: %s' % str(point_min))
        result_str = 'Result:' + point_min + ':' + str(minimum)
        return result_str


def send_update_to_gui(topic_arn: str, msg: str) -> None:
    groupid = 'group_id'  # str(uuid.uuid4().hex)
    response = sns.publish(
        TopicArn=topic_arn,
        Message=msg,
        MessageGroupId=groupid
    )
    # print(response['MessageId'])


def receive_message_from_sqs_queue() -> bool:
    response = sqs.receive_message(
        QueueUrl=queue_url,
        AttributeNames=[
            'SentTimestamp'
        ],
        MaxNumberOfMessages=1,
        MessageAttributeNames=[
            'All'
        ],
        VisibilityTimeout=3600,
        WaitTimeSeconds=0
    )
    if 'Messages' in response:
        message = response['Messages'][0]
        receipt_handle = message['ReceiptHandle']
        grid_size = message['MessageAttributes']['GridSize']['StringValue']
        topic_arn = message['MessageAttributes']['TopicArn']['StringValue']
        atom_values = json.loads(message['Body'])
        # Delete received message from queue
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        print('Received and deleted message: %s' % message)
        g_size = int(grid_size)
        max_val = g_size + 1
        s = np.array(range(1, max_val))
        points = np.vstack((ndmesh(s, s, s))).reshape(3, -1).T

        # result = calculate_effect_on_grid_point(1, 1, 1, atom_values, topic_arn)
        manager = mp.Manager()
        return_dict = manager.dict()

        if g_size > 4:
            i = 0
            processes = []
            n = 64
            parts = [points[i:i + n] for i in range(0, len(points), n)]

            while i < len(parts):
                part = parts[i]
                p = mp.Process(target=calculate_parallel, args=[part, atom_values, topic_arn, return_dict])
                p.start()
                processes.append(p)
                i += 1
            for p in processes:
                p.join()
            vals = list(return_dict.values())
            keys = list(return_dict.keys())
            minimum = min(vals)
            min_idx = vals.index(minimum)
            point = keys[min_idx]
            result = 'Result:'+point+':'+str(minimum)
            # print(return_dict.values())

        else:
            result = calculate_parallel(
                points,
                atom_values,
                topic_arn)
        send_update_to_gui(topic_arn, str(result))
        # print('Effect calculated: ' + str(result))
        # send_update_to_gui(topic_arn, 'Result:' + str(result))
        return False
    else:
        # print('No messages to receive.')
        return True


def say_something(something):
    print(something)


if __name__ == '__main__':
    while True:
        receive_message_from_sqs_queue()

