import folium
import json
from flask import Flask, render_template, Markup, request
from flask_sqlalchemy import SQLAlchemy
from folium.plugins import MarkerCluster
from datetime import datetime
import rescaler
import numpy as np
import pandas as pd

app = Flask(__name__)  # bridge.db, rain_msg.db 연동
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///bridge_db.db"
app.config['SQLALCHEMY_BINDS'] = {  # multiple databases
    'bridge_key': 'sqlite:///bridge_db.db',
    'rain_key': 'sqlite:///rain_msg.db'
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#################################################################


class Bridge(db.Model):
    __tablename__ = 'BRIDGE'
    __bind_key__ = 'bridge_key'  # multiple db의 bind key
    id = db.Column(db.Integer, primary_key=True)
    bridge_name = db.Column(db.Text)
    address = db.Column(db.Text)
    etc_address = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    brid_height_origin = db.Column(db.Float)
    location_start = db.Column(db.Text)
    wl_station_code = db.Column(db.Integer)
    station_name = db.Column(db.Text)
    location = db.Column(db.Text)
    obs_date = db.Column(db.DateTime)
    WL = db.Column(db.Float)
    bridge_height = db.Column(db.Float)


class Temp(db.Model):
    __tablename__ = 'TEMP'
    __bind_key__ = 'bridge_key'
    obs_date = db.Column(db.DateTime, primary_key=True, index=True)
    WL = db.Column(db.Float)


class Rain_msg(db.Model):
    # db.Model을 상속받으면 db.Column()메소드 사용 가능
    __tablename__ = 'RAIN_MSG'
    __bind_key__ = 'rain_key'  # multiple db의 bind key
    index = db.Column(db.Integer, primary_key=True)
    create_date = db.Column(db.Text)
    location_id = db.Column(db.Text)
    location_name = db.Column(db.Text)
    md101_sn = db.Column(db.Text)
    msg = db.Column(db.Text)


#################################################################


db.create_all(bind='bridge_key')  # 테이블 생성
db.create_all(bind='rain_key')


#################################################################


list_seoul = db.session.query(Bridge.latitude, Bridge.longitude,
                              Bridge.bridge_name, Bridge.bridge_height, Bridge.obs_date, Bridge.WL,
                              Bridge.address, Bridge.etc_address).group_by(Bridge.location_start).filter_by(address="서울특별시").all()

list_incheon = db.session.query(Bridge.latitude, Bridge.longitude,
                              Bridge.bridge_name, Bridge.bridge_height, Bridge.obs_date, Bridge.WL,
                              Bridge.address, Bridge.etc_address).group_by(Bridge.location_start).filter_by(address="인천광역시").all()

list_gyeonggi = db.session.query(Bridge.latitude, Bridge.longitude,
                              Bridge.bridge_name, Bridge.bridge_height, Bridge.obs_date, Bridge.WL,
                              Bridge.address, Bridge.etc_address).group_by(Bridge.location_start).filter_by(address="경기도").all()

brid_list = [ p for (p,) in db.session.query(Bridge.location_start).group_by(Bridge.location_start)] # 교량 목록


# MinMaxScaler가 없어서 대체
def rescale(input_list, newmin, newmax):
    oldmin = np.min(input_list)
    oldmax = np.max(input_list)
    oldrange = (oldmax - oldmin)
    newrange = (newmax - newmin)

    newlist = []
    for i in input_list:
        newi = (((i - oldmin) * newrange) / oldrange) + newmin
        newlist.append(newi)

    return newlist

# 크롤링해서 db에 넣어주는 작업 필요
# 우리는 12시간의 데이터를 쓸 거니까 -> [-12:]

def input_data():
    for i in range(1): # for i in range(len(brid_list))
        time = [p for (p,) in db.session.query(Bridge.obs_date).filter_by(location_start=brid_list[i])]
        value = [p for (p,) in db.session.query(Bridge.WL).filter_by(location_start=brid_list[i])]
        std_value = rescale(value, 0, 1)
        std_value = std_value[-12:]
        df = pd.DataFrame({'std_value':np.array(std_value)}, index=time[-12:])
        for j in range(12):
            df['shift_{}'.format(j)] = df['std_value'].shift(j)
        input_df = df.dropna().drop('std_value', axis=1)
        input_values = input_df.values
        input_data = input_values.reshape(input_values.shape[0], 12, 1)
        return input_data


#################################################################

@app.route('/predict', methods=['POST'])
def predict():
    return


@app.route('/home', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def home():
    status = request.args.get('status', '0')  # sidebar menu get value
    print(status)
    print(input_data())
    print(type(input_data()))

    #############################################################################

    area_value = None
    if request.method == 'POST':
        area_value = request.form['btn_area']  # button post value
    print(area_value)
    #############################################################################
    rain = Rain_msg.query.all()  # (SELECT * FROM 테이블명)과 동일함

    list_area = None
    if area_value == 'seoul':
        list_area = list_seoul
    elif area_value == 'incheon':
        list_area = list_incheon
    elif area_value == 'gyeonggi':
        list_area = list_gyeonggi

    print(list_area)  # list의 select 결과
    #############################################################################
    start_coords = (37.646495, 126.739804)  # 시작 좌표
    m = folium.Map(location=start_coords, zoom_start=9, width='100%')

    #############################################################################
    with open('sudo_geo.json', mode='rt', encoding='utf-8') as f:  # 수도권 지역 geojson 경계선 표시
        geo_sudo = json.loads(f.read())

    folium.GeoJson(
        geo_sudo,
        name='sudo_geo'
    ).add_to(m)
    #############################################################################
    folium_map = MarkerCluster().add_to(m)

    if list_area != None:
        for i in list_area:
            print(i.latitude, i.longitude)
            text = "이름: " + str(i.bridge_name) + "\n높이: " + str(i.bridge_height) + "\n수위: " + str(i.WL)
            pp_text = folium.IFrame(text, width=100, height=150)
            pp = folium.Popup(pp_text, max_width=1000)
            ic = folium.Icon(color='red', icon='info-sign')
            folium.Marker(
                location=[i.latitude, i.longitude],
                popup=pp,
                icon=ic,
            ).add_to(folium_map)
    #############################################################################
    _ = m._repr_html_()

    # get definition of map in body
    map_div = Markup(folium_map.get_root().html.render())  # html 소스를 리턴
    # html to be included in header
    hdr_txt = Markup(folium_map.get_root().header.render())
    # html to be included in <script>
    script_txt = Markup(folium_map.get_root().script.render())
    #############################################################################

    return render_template('index.html', status=status, map_div=map_div, hdr_txt=hdr_txt, script_txt=script_txt,
                           result_rain=rain, result_brid=list_area)


if __name__ == '__main__':
    app.run()
