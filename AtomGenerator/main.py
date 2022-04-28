#!/home/ubuntu/atomgen-app/.env/bin/python3
import random
import json
import boto3


# Create AWS clients
sqs = boto3.client('sqs')
sns = boto3.client('sns')
s3 = boto3.client('s3')

queue_url_receive = 'https://sqs.us-east-1.amazonaws.com/283893968322/queue.fifo'
queue_url_send = 'https://sqs.us-east-1.amazonaws.com/283893968322/queue2.fifo'

bucket_name = 'cc-a2-bucket'


# Send message to SQS queue
def send_message_to_grid_solver(grid_size: str, atoms: str, topic_arn: str, atoms_count: int) -> None:
    response = sqs.send_message(
        QueueUrl=queue_url_send,
        MessageAttributes={
            'GridSize': {
                'StringValue': grid_size,
                'DataType': 'Number'
            },
            'TopicArn': {
                'StringValue': topic_arn,
                'DataType': 'String'
            },
        },
        MessageGroupId="group_id",
        MessageBody=(
            atoms
        )
    )
    print(response['MessageId'])


def receive_message_from_sqs_queue() -> bool:
    response = sqs.receive_message(
        QueueUrl=queue_url_receive,
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
        print("ATTRIBUTES:")
        print(message['MessageAttributes'])
        grid_size = message['MessageAttributes']['GridSize']['StringValue']
        # grid_point = message['MessageAttributes']['GridPoint']['StringValue']
        topic_arn = message['MessageAttributes']['TopicArn']['StringValue']
        atoms_count = message['MessageAttributes']['AtomsCount']['StringValue']
        object_key = message['MessageAttributes']['StorageId']['StringValue']
        atoms = generate_atom_values(int(grid_size), int(atoms_count))
        add_atom_values_to_s3_object(atoms, object_key)
        # Delete received message from queue
        sqs.delete_message(
            QueueUrl=queue_url_receive,
            ReceiptHandle=receipt_handle
        )
        print('Received and deleted message: %s' % message)
        send_message_to_grid_solver(grid_size, atoms, topic_arn, atoms_count)
        return False
    else:
        # print('No messages to receive.')
        return True


def generate_atom_values(grid_size: int, atom_count: int) -> str:
    atoms = []
    i = 0
    while i < atom_count:
        atom = {
            'x': round(random.uniform(1, grid_size), 4),
            'y': round(random.uniform(1, grid_size), 4),
            'z': round(random.uniform(1, grid_size), 4),
            'e': round(random.uniform(0.1, 10), 4)
        }
        atoms.append(atom)
        i += 1
    print(json.dumps(atoms))
    return json.dumps(atoms)


def write_to_s3_bucket(obj, key: str) -> None:
    obj = json.dumps(obj)
    print('writing object...')
    response = s3.put_object(
        Body=obj,
        Bucket=bucket_name,
        Key=key,
        ContentType="application/json"
    )
    if 'Expiration' in response:
        expiration = response['Expiration']
        print('Object expires at %s' % expiration)


def read_s3_object(key: str):
    print('reading object...')
    response = s3.get_object(
        Bucket=bucket_name,
        Key=key,
        ResponseContentType="application/json"
    )
    if 'Body' in response:
        return response['Body'].read()
    else:
        print('no body in response object')


def add_atom_values_to_s3_object(atoms: str, key: str) -> None:
    object_to_update = json.loads(read_s3_object(key))
    atoms = json.loads(atoms)
    print('inserting atom values...')
    object_to_update['Atom values'] = atoms
    print(object_to_update)
    write_to_s3_bucket(object_to_update, key)

if __name__ == '__main__':
    while True:
        receive_message_from_sqs_queue()
