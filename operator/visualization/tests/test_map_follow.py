"""Exercise the shipped map script in Qt's JavaScript engine, without Internet."""
import json
from pathlib import Path

import pytest
from PySide6.QtQml import QJSEngine
from PySide6.QtWidgets import QApplication


STUB = r"""
var window=this, location={hash:""};
var performance={now:()=>0}, callbacks=[];
var requestAnimationFrame=fn=>{callbacks.push(fn);return callbacks.length;};
var cancelAnimationFrame=()=>{};
var document={getElementById:()=>({style:{}}),createElement:()=>({classList:{toggle:()=>{}}})};
window.addEventListener=()=>{};
var instances=0;
class FakeMap {
  constructor(options){this.options=options;this.handlers={};this.center=[0,0];this.moves=[];instances++;}
  on(event,fn){this.handlers[event]=fn;}
  areTilesLoaded(){return true;}
  jumpTo(options){this.center=options.center;this.moves.push(options);}
  easeTo(options){if(options.center)this.center=options.center;this.moves.push(options);}
  getCenter(){return {toArray:()=>this.center};}
  getZoom(){return 16;}
  getLayer(id){return true;}
  setPaintProperty(id,key,value){this[id+':'+key]=value;}
  getFilter(id){return ['all',['<=',['get','ref_length'],6],['==',['get','network'],'test']];}
  getStyle(){return {layers:[{id:'road_shield_us',filter:this.getFilter()}]};}
  setFilter(id,value){this[id+':filter']=value;}
  resize(){}
}
class FakeMarker {
  constructor(options){this.options=options;this.position=[0,0];this.rotation=0;}
  setLngLat(value){this.position=value;return this;}
  setRotation(value){this.rotation=value;return this;}
  addTo(map){return this;}
  getLngLat(){return {lng:this.position[0],lat:this.position[1]};}
  getRotation(){return this.rotation;}
  getElement(){return this.options.element;}
}
var maplibregl={Map:FakeMap,Marker:FakeMarker};
function flush(){var pendingCallbacks=callbacks;callbacks=[];pendingCallbacks.forEach(fn=>fn(200));}
"""


@pytest.fixture
def js():
    app = QApplication.instance() or QApplication([])
    engine = QJSEngine()
    source = Path("visualization/gui/assets/navigation.js").read_text()
    # QJSEngine evaluate scopes top-level let/const to each evaluation. Expose
    # handles only in this harness; the shipped script remains unmodified.
    source += "\nwindow.map=map;window.marker=marker;window.demoStyle=demoStyle;window.numericFilter=numericFilter;"
    for script in (STUB, source, 'map.handlers["style.load"]();map.handlers.load();'):
        result = engine.evaluate(script)
        assert not result.isError(), result.toString()
    yield engine
    del engine


def evaluate(engine, script):
    result = engine.evaluate(script)
    assert not result.isError(), result.toString()
    return result.toVariant()


def position(engine, lat=35, lon=-97, course=90, stale=False):
    value = dict(lat=lat, lon=lon, course=course, stale=stale)
    evaluate(engine, "receivePosition(" + json.dumps(value) + ");flush();")


def test_light_style_without_old_woodland_texture(js):
    assert evaluate(js, "map.options.style") == "https://tiles.openfreemap.org/styles/positron"
    assert evaluate(js, "demoStyle().layers[0].paint['background-color']") == "#eeece7"
    assert evaluate(js, "marker.options.element.innerHTML").startswith('<svg')
    assert evaluate(js, "navigationStatus.marker") == "triangle"


def test_moving_vehicle_keeps_camera_centered_without_recreation(js):
    position(js)
    for i in range(1, 30):
        position(js, lon=-97+i*.00005)
        assert evaluate(js, "map.center") == pytest.approx([-97+i*.00005, 35])
        assert evaluate(js, "marker.position") == pytest.approx([-97+i*.00005, 35])
    assert evaluate(js, "instances") == 1
    assert evaluate(js, "navigationStatus.cameraMoves") == 30
    assert evaluate(js, "map.moves[29].duration") == 180


def test_stationary_noise_does_not_move_or_rotate(js):
    position(js)
    for i in range(20):
        position(js, lat=35+(i%2)*.000004, course=i*15)
    assert evaluate(js, "navigationStatus.cameraMoves") == 1
    assert evaluate(js, "marker.position") == [-97, 35]
    assert evaluate(js, "marker.rotation") == 90


def test_small_steps_accumulate_until_movement_is_meaningful(js):
    position(js)
    for i in range(1, 10):
        position(js, lon=-97+i*.000003)
    assert evaluate(js, "navigationStatus.cameraMoves") == 2
    assert evaluate(js, "map.center[0]") > -97


def test_real_pan_suspends_follow_and_recenter_forces_it_back_on(js):
    position(js)
    evaluate(js, "map.handlers.dragstart({originalEvent:{type:'mousedown'}});map.center=[-98,34];")
    position(js, lon=-96.99)
    assert evaluate(js, "navigationStatus.follow") is False
    assert evaluate(js, "map.center") == [-98, 34]
    assert evaluate(js, "marker.position") == [-96.99, 35]
    evaluate(js, "recenter();flush();")
    assert evaluate(js, "navigationStatus.follow") is True
    assert evaluate(js, "map.center") == [-96.99, 35]
    position(js, lon=-96.98)
    assert evaluate(js, "map.center") == [-96.98, 35]


def test_programmatic_drag_does_not_disable_follow(js):
    position(js)
    evaluate(js, "map.handlers.dragstart({});")
    position(js, lon=-96.99)
    assert evaluate(js, "navigationStatus.follow") is True
    assert evaluate(js, "map.center") == [-96.99, 35]


def test_cached_stale_position_does_not_drive_camera(js):
    position(js)
    position(js, lon=-96, stale=True)
    assert evaluate(js, "map.center") == [-97, 35]
    assert evaluate(js, "navigationStatus.cameraMoves") == 1


def test_missing_course_holds_last_bearing(js):
    position(js, course=75)
    position(js, lon=-96.99, course=None)
    assert evaluate(js, "marker.rotation") == 75
    assert evaluate(js, "map.moves[1].bearing") == 75


def test_navigation_palette_has_readable_roads_and_water(js):
    assert evaluate(js, "map['highway_minor:line-color']") == '#8d9da8'
    assert evaluate(js, "map['water:fill-color']") == '#b6d7e8'
    assert evaluate(js, "map['background:background-color']") == '#eeece7'


def test_unnumbered_roads_do_not_request_invalid_shields(js):
    result=evaluate(js, "map['road_shield_us:filter']")
    assert result == ['all', ['<=', ['to-number', ['coalesce', ['get', 'ref_length'], 7], 7], 6], ['==', ['get', 'network'], 'test']]
    assert evaluate(js, "numericFilter(['>=',['get','rank'],3])") == ['>=',['to-number',['coalesce',['get','rank'],2],2],3]
