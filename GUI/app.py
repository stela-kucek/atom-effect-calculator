#!/home/ubuntu/gui-app/.env/bin/python3
from flask import Flask, request, render_template, Response, session
import boto3
import uuid
import os
import json

# Create AWS clients
sqs = boto3.client('sqs')
sns = boto3.client('sns')
s3 = boto3.client('s3')
iam = boto3.client('iam')

queue_url = 'https://sqs.us-east-1.amazonaws.com/283893968322/queue.fifo'
# queue_url_subscription = 'https://sqs.us-east-1.amazonaws.com/283893968322/queue1.fifo'
queue_arn_subscription = 'arn:aws:sqs:us-east-1:283893968322:'

bucket_name = 'cc-a2-bucket'

app = Flask(__name__)
app.secret_key = os.urandom(16)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


def create_sns_topic() -> str:
    topic_id = str(uuid.uuid4().hex) + '.fifo'
    response_sns = sns.create_topic(
        Name=topic_id,
        Attributes={
            'FifoTopic': 'true',
            'ContentBasedDeduplication': 'true'
        },
    )
    topic_arn = response_sns['TopicArn']
    # app.config.update(TOPIC_ARN=topic_arn)
    session['topic_name'] = topic_id
    session['topic'] = topic_arn
    return topic_arn
    # print(topic_arn)


def create_sqs_queue():
    queue_name = 'queue_' + session['topic_name']
    session['queue_arn'] = queue_arn_subscription + queue_name	
    policy = {
	  "Version": "2012-10-17",
	  "Statement": [
	    {
	      "Sid": "Stmt1607786767347",
	      "Effect": "Allow",
	      "Principal": {
	        "AWS": "*"
	      },
	      "Action": "sqs:SendMessage",
	      "Resource": session['queue_arn']
	    }
	  ]
	}
    response = sqs.create_queue(
	    QueueName=queue_name,
	    Attributes={
	        'FifoQueue': 'true',
	        'ContentBasedDeduplication': 'true',
	        'Policy': json.dumps(policy)
	    },
    )
    queue_url_sub = response['QueueUrl']
    session['queue_url'] = queue_url_sub



# def add_permission_to_sub_queue():
# 	policy = {
# 	  "Version": "2012-10-17",
# 	  "Statement": [
# 	    {
# 	      "Sid": "Stmt1607786767347",
# 	      "Effect": "Allow",
# 	      "Principal": {
# 	        "AWS": "*"
# 	      },
# 	      "Action": "sqs:SendMessage",
# 	      "Resource": session['queue_arn']
# 	    }
# 	  ]
# 	}
#     response = sqs.add_permission(
# 	    QueueUrl=session['queue_url'],
# 	    Label='AllowSendingToQueue',
# 	    AWSAccountIds=[
# 	    "aws:*"
# 	    ],
# 	    Actions=[
# 	        'SendMessage',
# 	    ]
# 	)
    
#     response = iam.create_policy(
# 	    PolicyName='sqs_policy',
# 	    PolicyDocument=json.dumps(policy),
# 	)



def delete_sns_topic(topic):
    # topic = session['topic']
    response = sns.delete_topic(
    	TopicArn=topic,
    	)
    print('Topic with arn %s deleted' % topic)


def delete_all_topic_subscriptions(topic):
    # topic = session['topic']
    response = sns.list_subscriptions_by_topic(
        # TopicArn=app.config['TOPIC_ARN'],
        TopicArn=topic,
    )
    if 'Subscriptions' in response:
        subscriptions = response['Subscriptions']
        for s in subscriptions:
            s_arn = s['SubscriptionArn']
            sns.unsubscribe(
                SubscriptionArn=s_arn
            )
        print('Unsubscribed from topic %s.' % topic)
    else:
        print('There were no subscriptions for this topic.')


def delete_sub_queue(queue):
    response = sqs.delete_queue(
	    QueueUrl=queue
	)
    print('Queue deleted.')


def write_to_s3_bucket(obj: dict, key: str) -> None:
    body = json.dumps(obj)
    print('writing object...')
    response = s3.put_object(
        Body=body,
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
        Key=key
    )
    if 'Body' in response:
        return response['Body'].read()
    else:
        print('no body in response object')


def add_result_to_s3_object(result: str, key: str) -> None:
    object_to_update = json.loads(read_s3_object(key))
    print('updating result value...')
    object_to_update['Result'] = result
    print(object_to_update)
    write_to_s3_bucket(object_to_update, key)


def subscribe_to_topic(topic_arn: str) -> None:
    queue_arn = session['queue_arn']
    response = sns.subscribe(
        TopicArn=topic_arn,
        Protocol='sqs',
        Endpoint=queue_arn,
    )
    print('Subscribed to topic:')
    print(response['SubscriptionArn'])


@app.route('/progress')
def progress():
    maximum = session['maximum']
    print('max:')
    print(maximum)
    obj = session['object']
    topic = session['topic']
    queue = session['queue_url']
    def generate(topic, queue):
        x = 0
        update = receive_message_from_sqs_queue(queue)
        while update == 0 or update == 1:
            val = round(x / int(maximum) * 100, 2)
            yield "data:" + str(val) + "\n\n"
            x = x + update
            update = receive_message_from_sqs_queue(queue)
            # time.sleep(0.5)
        yield "data:Result:" + str(update) + "\n\n"
        add_result_to_s3_object(update.replace(':', ', '), obj)
        delete_all_topic_subscriptions(topic)
        delete_sns_topic(topic)
        delete_sub_queue(queue)
    return Response(generate(topic, queue), mimetype='text/event-stream')


def receive_message_from_sqs_queue(queue_url_subscription):
    response = sqs.receive_message(
        QueueUrl=queue_url_subscription,
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
    #print('RESPONSE:')
    #print(response)
    if 'Messages' in response:
        message = response['Messages'][0]
        receipt_handle = message['ReceiptHandle']
        if 'Result' not in message['Body']:
            sqs.delete_message(
                QueueUrl=queue_url_subscription,
                ReceiptHandle=receipt_handle
            )
            print('Received update and deleted message: %s' % message)
            return 1.0
        else:
            res = message['Body']
            dict_res = json.loads(res)
            value = str(dict_res['Message'])
            value = value.split(":")
            sqs.delete_message(
                QueueUrl=queue_url_subscription,
                ReceiptHandle=receipt_handle
            )
            print('Received result and deleted message: %s' % message)
            return value[1]+':'+value[2]
    else:
        # print('No update received from GridSolver.')
        return 0


@app.route('/calculator', methods=['POST'])
def calc():
    atoms = request.form['atoms_count']
    session['atoms'] = atoms
    topic_arn = create_sns_topic()
    create_sqs_queue()
    # add_permission_to_sub_queue()
    subscribe_to_topic(topic_arn)
    grid_size = int(request.form['grid_size'])
    max_progress_value = grid_size*grid_size*grid_size
    session['maximum'] = max_progress_value
    object_key = 'object_'+str(uuid.uuid4().hex)
    #app.config.update(OBJECT_KEY=object_key)
    session['object'] = object_key
    # write object to s3:
    body = {'Grid size': grid_size, 'Atom count': atoms, 'Atom values': '', 'Result': ''}
    write_to_s3_bucket(body, object_key)

    response_sqs = sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            'GridSize': {
                'StringValue': str(grid_size),
                'DataType': 'Number'
            },
            'TopicArn': {
                'StringValue': topic_arn,
                'DataType': 'String'
            },
            'AtomsCount': {
                'StringValue': atoms,
                'DataType': 'Number'
            },
            'StorageId': {
                'StringValue': object_key,
                'DataType': 'String'
            },
        },
        MessageGroupId="group_id",
        MessageBody=(
            'Grid information for fulfilling user request '+topic_arn
        )
    )
    print(response_sqs['MessageId'])

    return render_template('result.html', max_value=max_progress_value)


if __name__ == '__main__':
    #app.config['TOPIC_ARN'] = ''
    #app.config['OBJECT_KEY'] = ''
    app.run(host='0.0.0.0', port=8080)
