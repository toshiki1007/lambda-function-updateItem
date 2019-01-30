import boto3
from boto3.session import Session
from boto3.dynamodb.conditions import Key,Attr
import json
import datetime
import urllib.request
import layer
import os
import requests

region = "us-west-2"
session = Session(
    region_name=region
)
dynamodb = session.resource('dynamodb')
user_table = dynamodb.Table('User')
item_table = dynamodb.Table('Item')

update_balance_url = os.environ['UPDATE_BALANCE_URL']
method = "POST"
headers = {
    'Content-Type': 'application/json',
}

ses_client = boto3.client('ses')

layer.patch_all

def response(status_code, update_record, error_msg):
    return {
        'statusCode': status_code,
        'body': update_record,
        'errorMessage': error_msg
    }

def update_item(item_id, buyer_id):
    item_table.update_item(
        Key = {
            'itemId': item_id,
        },
        UpdateExpression = 'SET buyerId = :buyerId, sellingDate = :sellingDate',
        ConditionExpression = Attr('buyerId').eq('None'),
        ExpressionAttributeValues = {
            ':buyerId': buyer_id,
            ':sellingDate': '{0:%Y-%m-%d}'.format(datetime.datetime.now()),
        },
        ReturnValues='ALL_NEW'
    )
    
    new_record = item_table.get_item(
        Key={
            'itemId': item_id,
        }
    )['Item']
    
    return new_record
    
def role_back_item(item_id):
    item_table.update_item(
        Key = {
            'itemId': item_id,
        },
        UpdateExpression = 'SET buyerId = :buyerId, sellingDate = :sellingDate',
        ExpressionAttributeValues = {
            ':buyerId': 'None',
            ':sellingDate': '9999-99-99',
        },
        ReturnValues='ALL_NEW'
    )
    
    role_back_record = item_table.get_item(
        Key={
            'itemId': item_id,
        }
    )['Item']
    
    return role_back_record

def send_email(email_address, email_subject, email_body):
    ses_client.send_email(
            Source='rhapsody777jp@yahoo.co.jp',
            Destination={
                'ToAddresses': [
                    email_address,
                ]
            },
            Message={
                'Subject': {
                    'Data': email_subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': email_body,
                        'Charset': 'UTF-8'
                    }
                }
            },
            ReplyToAddresses=[
                'rhapsody777jp@yahoo.co.jp',
            ]
        )

def lambda_handler(event, context):
    buyer_id = event['userId']
    item_id = event['itemId']
    
    update_record = item_table.get_item(
        Key={
            'itemId': item_id,
        }
    )['Item']

        
    #商品情報更新
    try:
        new_record = update_item(item_id, buyer_id)
    except:
        return response(400, update_record, 'invalid update item')

    #残高＆履歴更新
    update_balance_input = {
        'userId': buyer_id,
        'tradingUserId': update_record['sellerId'],
        'price': str(update_record['price']),
        'typeFlg': '1'
    }
    
    update_balance_input_json = json.dumps(update_balance_input).encode("utf-8")
    update_balance_response = requests.post(update_balance_url, update_balance_input_json,headers=headers).json()
    
    if update_balance_response['statusCode'] == 400:
        #商品テーブルをロールバック
        role_back_record = role_back_item(item_id)
        return response(400, role_back_record, update_balance_response['message'])
        
    user = user_table.get_item(
        Key={
            'userId': update_record['sellerId'],
        }
    )['Item']
    
    email_address = user['mail']
    email_subject = '販売完了通知'
    email_body = '商品ID：' + item_id + 'が購入されました'
    send_email(email_address, email_subject, email_body)

    return response(200, new_record, None)