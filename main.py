from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import pay
import lcd
import socket

I2CLCD = lcd.LoopDisplay(1,0x27)
pay.lcdShow = I2CLCD.show
#pay.SERVER_IP = socket.gethostbyname(socket.gethostname())
pay.SERVER_IP = '219.85.47.171:5000'
I2CLCD.show("Webserver start  " + pay.SERVER_IP) 
http_server = HTTPServer(WSGIContainer(pay.app))
http_server.listen(5000)
IOLoop.instance().start()
