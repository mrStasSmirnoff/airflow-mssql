#!/bin/bash
echo "Initializing DB..."
airflow db init
 
echo "Adding admin user..."
airflow users create -u ${AIRFLOW_ADMIN_USERNAME} -p ${AIRFLOW_ADMIN_PASSWORD} -f ${AIRFLOW_ADMIN_FIRSTNAME} -l ${AIRFLOW_ADMIN_LASTNAME} -e ${AIRFLOW_ADMIN_EMAIL} --r Admin

echo "Starting webserver and scheduler..."
airflow webserver & airflow scheduler & wait -n
# pkill -P $$
sleep 300