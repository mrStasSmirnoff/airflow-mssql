from datetime import datetime, timedelta
from airflow import DAG
from airflow.hooks.mssql_hook import MsSqlHook
from airflow.operators.python_operator import PythonOperator

from airflow.models import Variable

import requests
from xml.etree import ElementTree

import pandas as pd
#import the relevant sql library 
from sqlalchemy import create_engine

import pyodbc
from datetime import datetime, timedelta, date

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2020, 5, 8),
    'email': ['mr.stassmirnoff@yandex.ru'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'ETL_TO_MSSQL',
    default_args=default_args,
    schedule_interval='0 12 * * *'
)

def push_to_xcom(ti, key, value):
    ti.xcom_push(key=key, value=value)


def get_from_xcom(ti, key, task_ids):
    return ti.xcom_pull(key=key, task_ids=task_ids)



# further define as env varibles in config file for Airflow
login = 'admin'
password = 'f39d93cc55b135ab1f67e98bd4c64a2e18f8db66'

url = 'https://zurrahmat-co.iiko.it:443/resto/api/auth?login={}&pass={}'.format(login,password)

def extract_data_from_api(url: str, **kwargs):
    try:
        response = requests.get(url)

        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except Exception as err:
        print(f'Other error occurred: {err}')  # Python 3.6
    else:
        print('Success!')

    key_value = response.text

    end = (date.today()).strftime('%d.%m.%Y')
    start = (date.today() - timedelta(days=720)).strftime('%d.%m.%Y')

    response_xml = requests.get(
        'https://zurrahmat-co.iiko.it:443/resto/api/reports/olap?key={}' \
        '&report=SALES&from={}&to={}&groupRow=OpenDate.Typed&groupRow=DishName&agr=DishAmountInt'
        .format(key_value, start, end))

    string_xml = response_xml.content
    root = ElementTree.fromstring(string_xml)

    push_to_xcom(kwargs['ti'], key='mssql_dw_query_result', value=root)


def transform_data(root, **kwargs) -> pd.DataFrame:

    ti = kwargs['ti']
    root = get_from_xcom(ti, 'extracted_data', query_api_task.taks_id)

    datetime_list = [child.text for child in root.iter('OpenDate.Typed')]
    dish_amount_list = [child.text for child in root.iter('DishAmountInt')]
    dish_name = [child.text for child in root.iter('DishName')]

    df_ = pd.DataFrame(list(zip(datetime_list, dish_amount_list, dish_name)),
                    columns=['DateTime', 'DishItems','DishName'])

    push_to_xcom(kwargs['ti'], key='transformed_data', value=df_)


def write_data_to_mssql(df, **kwargs):
    # config.py for MSSQL

    #db_type = 'mssql+pyodbc',
    #user = 'resto',
    #password = 'resto#test',
    #host = 'ufa.arbus.biz',
    #port = '11201',
    #database = 'test'
    table_name = 'meals_zurrahmat_test'
    schema = 'dbo'

    ti = kwargs['ti']
    df = get_from_xcom(ti, 'extracted_data', transform_data_task.taks_id)
    mssql_hook = MsSqlHook(mssql_conn_id='meals_mssql')
    engine = mssql_hook.get_sqlalchemy_engine()
    #CNN_MSSQL = create_engine('mssql+pyodbc://resto:resto#test@ufa.arbus.biz,11201/test?driver=ODBC+Driver+17+for+SQL+Server')

    df.to_sql(table_name, con=engine, if_exists='append',index=True, schema=schema, method='multi', chunksize=50)


query_api_task	= PythonOperator(task_id='query_api_task', 
                            python_callable=extract_data_from_api,
                            dag=dag)

transform_data_task = PythonOperator(task_id='transform_data',
                            python_callable=transform_data,
                            dag=dag)

save_to_mssql = PythonOperator(task_id='load_data', 
                            python_callable=write_data_to_mssql,
                            dag=dag)

query_api_task >> transform_data_task >> save_to_mssql