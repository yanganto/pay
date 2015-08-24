from flask import Flask, make_response, request, render_template, jsonify, url_for
from socket import gethostbyname, gethostname
from jinja2 import Environment, FileSystemLoader 

from wtforms.ext.sqlalchemy.orm import model_form
from flask_wtf import Form
from wtforms import TextField
from flask.ext.sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields, ValidationError

import random

app = Flask(__name__)

#### SQLAlchemy Settings ####
app.config['SECRET_KEY'] = 'pausecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
#app.config['SQLALCHEMY_ECHO'] = True
app.config['SQLALCHEMY_ECHO'] = False 

#### Jinja2 environment ####
env = Environment()
env.loader = FileSystemLoader('./templates')

#### LCD show message function ###
SERVER_IP="192.168.0.0"

def lcdShow( msg ):
    I2CLCD.show(msg)

db= SQLAlchemy(app)

#### Models ####
class Meal(db.Model):
    __tablename__ = 'meal'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Integer, nullable=False)

    def __init__(self, name, price):
        self.name = name
        self.price = price

    def __repr__(self):
         return str(self.name) + "(" + str(self.price) + ")"
    
    def url(self):
        return url_for('.meals', meals_id=self.id)

MealForm= model_form(Meal, base_class=Form)

class Table(db.Model):
    __tablename__='table'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(3), nullable=False)
    description = db.Column(db.String(50), nullable=False)

    def __init__(self, description):
        code = ""
        for i in range(3):
            code += random.choice('abcdefghijklmnopqrstuvwxyz1234567890')
        self.code = code
        self.description = description
    
    def __repr__(self):
        if self.description:
            return str(self.id) + "(" + self.code + "):" + self.description
        return str(self.id) + "(" + self.code + ")"

    def orderUrl(self):
        return 'http://' + SERVER_IP + url_for( '.orders', orders_code=self.code)

    def url(self):
        return url_for('.qr', qr_id=self.id)

class TableDescriptionForm(Form):
    description = TextField('description')

class State(db.Model):
    __tablename__ = 'state'
    id = db.Column( db.Integer, primary_key=True )
    name = db.Column(db.String(10), nullable=False)

    def __init__(self, name):
        self.name = name

class Order(db.Model):
    __tablename__='order'
    
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table.id'))
    table = db.relationship("Table")
    meal_id = db.Column(db.Integer, db.ForeignKey('meal.id'))
    meal = db.relationship("Meal")
    amount = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(50), nullable=False)
    state_id = db.Column(db.Integer, db.ForeignKey('state.id'))
    state = db.relationship("State")

    def __init__( self, table, meal, amount=1, comment=''):
        self.table=table
        self.meal=meal 
        self.amount=amount
        self.comment=comment
        self.state_id=1

    def __repr__(self):
        return str(self.table_id) + str(self.meal_id) + str(self.amount) + str(self.comment)


db.create_all()

#### Serialize Model ####
class MealSchema(Schema):
    _url = fields.Method("meals_url")
    def meals_url(self, meal):
        return meal.url()
    class Meta:
        fields = ('id', 'name', 'price', '_url')

meal_schema = MealSchema()
meals_schema = MealSchema(many=True)

class TableSchema(Schema):
    url = fields.Method("tables_url")
    orderUrl = fields.Method("tables_orderUrl")
    def tables_url(self, table):
        return table.url()
    def tables_orderUrl(self, table):
        return table.orderUrl()
    class Meta:
        fields = ('id', 'description', 'url', 'orderUrl')

table_schema = TableSchema()
tables_schema = TableSchema(many=True)


class OrderSchema(Schema):
    table_description = fields.Method("getTableDescription")
    meal_name= fields.Method("getMealName")
    meal_price= fields.Method("getMealPrice")
    state_name= fields.Method("getOrderState")
    def getTableDescription(self, order):
        return order.table.description
    def getMealName(self, order):
        return order.meal.name
    def getMealPrice(self, order):
        return order.meal.price
    def getOrderState(self, order):
        return order.state.name
    class Meta:
        fields = ('id', 'table_id', 'amount', 'comment', 'table_description', 'meal_name', 'meal_price', 'state_name', 'state_id')

orders_schema = OrderSchema(many=True)

#### Controls ####
@app.route('/')
def index():
    return render_template( 'index.html', title='Index')

@app.route("/QR/", methods=["GET"])
@app.route('/QR/<int:qr_id>', methods=["GET", "POST"])
def qr( qr_id=None ):
    if qr_id:
        if request.method == "GET":
            width = request.args.get('width', '800')
            height = request.args.get('height', '600')
            table = db.session.query(Table).filter(Table.id == qr_id).first()
            if table is None:
                return jsonify({'msg': 'None'}), 404
            svg = render_template( str(qr_id) + '.svg', width=width, height=height)
            response = make_response(svg)
            response.content_type = 'image/svg+xml'
            return response
        if request.method == "POST":
            if qr_id > 20 : qr_id =20
            total = db.session.query(Table).count()
            import pyqrcode
            for i in range( qr_id - total ):
                table = Table( str( total + i + 1)  )
                db.session.add(table)            
                qr = pyqrcode.create( table.orderUrl())
                qr.svg('templates/' + str( total + i + 1) + '.svg', scale=8)
            else:
                db.session.commit()
            table = db.session.query(Table).filter(Table.id == qr_id).first()
            form = TableDescriptionForm(request.form)
            form.validate() 
            table.description = form.description
            form.populate_obj( table)
            db.session.add(table)
            db.session.commit()
    if request.is_xhr:
        tables = db.session.query(Table)
        result = tables_schema.dump(tables)
        return jsonify({'tables': result.data})
    return render_template('QRs.html', form=TableDescriptionForm(), title='QR') 

@app.route("/delivery/", methods=["GET"])
@app.route("/delivery/<int:order_id>", methods=["GET", "PUT", "DELETE"])
def delivery( order_id=None ):
    if request.is_xhr:
        if request.method == 'PUT':
            order = db.session.query(Order).filter(Order.id == order_id).first()
            if order: 
                order.state_id += 1
                db.session.add(order)
                db.session.commit()
                return jsonify({"msg":"訂單狀態更新為" + order.state.name})
            return jsonify({"msg": "訂單不存在"}), 404
        if request.method =='DELETE':
            orders = db.session.query(Order).filter(Order.table_id == order_id)
            for order in orders:
                if order.state_id < 3:return jsonify({"msg":"有餐點尚未出餐"}), 405
                order.state_id = 4    
                db.session.add(order)
            else:
                db.session.commit()
            return jsonify({"msg":"結帳成功"})
        if order_id: # GET xhr with table_id
            orders = db.session.query(Order).filter(Order.table_id == order_id)
        else:
            orders = db.session.query(Order).filter(Order.state_id < 3)
        if orders.count() == 0: return jsonify({"msg":"沒有訂單"}), 404
        result = orders_schema.dump(orders)
        return jsonify({'orders': result.data})
    return render_template('delivery.html', title='Delivery', table_num = db.session.query(Table).count())
            
@app.route("/orders/")
@app.route("/orders/<string:orders_code>", methods=["GET", "POST", "DELETE"])
def orders(orders_code=None):
    table = db.session.query(Table).filter(Table.code == orders_code).first()
    if table:
        if request.method == 'GET':
            if request.is_xhr:
                orders = db.session.query(Order).filter(Order.table_id == table.id)
                if orders.count() == 0 : return jsonify({"msg": "您尚未下訂任何餐點"}), 404
                result = orders_schema.dump(orders)
                return jsonify({'orders': result.data})
        if request.method == 'POST':
            for meal_id in request.form.getlist('meals'):
                meal = db.session.query(Meal).filter(Meal.id == str(meal_id)).first()
                amount = request.form['amount'+ meal_id]
                db.session.add( Order(table, meal, amount, request.form['comment' + meal_id]))
            else:
                db.session.commit() 
                lcdShow("!!A new order!! Table " + str(table.id)) 
        if request.method == 'DELETE' and request.is_xhr:
            order_id = request.args.get('order_id')
            order = db.session.query(Order).filter(Order.id == order_id).first()
            if order and order.table.id == table.id and order.state_id == 1:
                db.session.delete(order)
                db.session.commit()
                return jsonify({"msg": "餐點已取消"})
            return jsonify({"msg": "訂單無法取消（已製作）"}), 404
        return render_template('orders.html', code=orders_code, title="Order", tableDes=table.description)
    return "<h1>請掃描桌上的QR條碼或輸入正確的網址。</h1>" 

@app.route("/meals/", methods=["GET", "POST"])
@app.route("/meals/<int:meals_id>", methods=["GET", "PUT", "DELETE"])
def meals( meals_id=None):
    if request.method == 'GET':
        if meals_id:
            meal = db.session.query(Meal).filter(Meal.id == meals_id).first()
            if request.is_xhr:
                if meal is None:
                    return jsonify({"msg":"餐點不存在"}), 404
            return render_template('meal.html', meal=meal, 
                   form=MealForm(obj=meal), title="Meal::"+meal.name)
        else:
            if request.is_xhr:
                queryset = db.session.query(Meal)
                if queryset.count() == 0 : return jsonify({"msg": "本店暫無餐點提供"}), 404
                result = meals_schema.dump(queryset)
                return jsonify({'meals': result.data})
    elif request.method == 'POST' and request.is_xhr:
        form = MealForm(request.form)
        if form.validate():
            meal = Meal( form.name, form.price)
            form.populate_obj(meal)
            db.session.add(meal)
            db.session.commit()
            return jsonify({"msg": "餐點新增成功"})
        return jsonify({"msg": "資料不正確"}), 400
    elif request.method == 'PUT' and request.is_xhr:
        meal = db.session.query(Meal).filter(Meal.id == meals_id).first()
        if meal is None: 
            return jsonify({"msg":"欲修改的餐點不存在（已被刪除）"}), 404
        form = MealForm(request.form, obj=meal)
        if form.validate():
            meal.name = form.name
            meal.price = form.price
            form.populate_obj(meal)
            db.session.add(meal)
            db.session.commit()
            return jsonify({"msg":"餐點修改完成"})
        return jsonify({"msg":"資料不正確"}), 400
    elif request.method == 'DELETE' and request.is_xhr :
        meal = db.session.query(Meal).filter(Meal.id == meals_id).first()
        if meal:
            db.session.delete(meal)
            db.session.commit()
            return jsonify({"msg": "餐點成功刪除"})
        return jsonify({"msg":"欲修改的餐點不存在（已被刪除）"}), 404
    return render_template('meals.html', form=MealForm(), 
                            title="Meal::List")

@app.route("/init/", methods=["GET","PUT", "DELETE"]) 
def init():
    if request.is_xhr:
        if request.method == 'PUT':
            import os.path
            if os.path.isfile('init.lck'):
                return jsonify({"msg": "資料庫已存在"})
            dic = {
                    "勁辣雞腿堡" : 50,
                    "紅茶" : 15,
                    "太陽蛋":20
                }
            for key, value in dic.items():
                meal = Meal( key, value)
                db.session.add(meal)
            else:
                db.session.commit()
            db.session.add(Table('第一桌'))
            db.session.add(State('已下訂')) #1
            db.session.add(State('準備中')) #2
            db.session.add(State('已出餐')) #3
            db.session.add(State('已結帳')) #4
            db.session.commit()
            table = db.session.query(Table).first()
            import pyqrcode
            qr = pyqrcode.create( table.orderUrl())
            qr.svg('templates/1.svg', scale=8)
            meal = db.session.query(Meal).first()
            db.session.add(Order(table, meal, 1, "不要洋蔥"))
            meal = db.session.query(Meal)[-1]
            db.session.add(Order(table, meal))
            db.session.commit()
            f = open('init.lck', 'w')
            return jsonify({"msg": "餐資料初始化完成"})
        elif request.method == 'DELETE':
            db.session.query(Order).delete()            
            db.session.commit()
            return jsonify({"msg":"訂單清除成功"}) 
        orders = db.session.query(Order)
        if orders.count() == 0: return jsonify({"msg":"無訂單"}), 404
        result = orders_schema.dump(orders)
        return jsonify({"orders": result.data})
    return render_template('init.html', title='Database')
        

if __name__ == '__main__':
    import lcd
    import os.path
    I2CLCD = lcd.LoopDisplay(1, 0x27)
    SERVER_IP = gethostbyname(gethostname())
    I2CLCD.show("Webserver start  " + SERVER_IP)
    app.debug = True
    app.run(host='0.0.0.0')
