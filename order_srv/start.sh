srv_name="order_srv_server"
chmod +x ./$srv_name.py
#重启，如果已经存在则关闭重启
PIDS=`ps -ef |grep ${srv_name} |grep -v grep | awk '{print $2}'`
if [ "$PIDS" != "" ];
then
  echo "${srv_name} is running"
  echo "shutting down ${srv_name}"
  ps -aux | grep $srv_name |grep -v grep | awk '{print $2}' | xargs kill $1
  echo "starting ${srv_name}"
  /root/.virtualenvs/mxshop_srv/bin/pip install -r requirements.txt -i https://pypi.douban.com/simple
  /root/.virtualenvs/mxshop_srv/bin/python $srv_name.py --ip=192.168.101.13 > /dev/null 2>&1 &
  echo "start ${srv_name} success"
else
  echo "starting ${srv_name}"
  	/root/.virtualenvs/mxshop_srv/bin/pip install -r requirements.txt -i https://pypi.douban.com/simple
    /root/.virtualenvs/mxshop_srv/bin/python $srv_name.py --ip=192.168.101.13 > /dev/null 2>&1 &
  echo "start ${srv_name} success"
fi