import os
from flask import Flask, render_template, jsonify, request
import pandas as pd
from neo4j import GraphDatabase
from py2neo import Graph
from dash import Dash, dash_table, html
import networkx as nx
import scipy


# Neo4j login - make sure to put neo4j+ssc in.
url = os.environ['NEO4j_URL']
username = "neo4j"
password = os.environ['NEO4j_PASSWORD']
url_graph = os.environ['NEO4j_GRAPH_URL']


# Connect to py2neo and neo4j
driver = GraphDatabase.driver(uri=url, auth=(username, password))
session = driver.session()
neo_graph = Graph(url, auth=(username, password))


# Voor buildings_network.html
query_designs = """
MATCH(n:Design_implementation)
RETURN n.implemented_design_strategies as Design
"""
result_designs = neo_graph.query(query_designs).to_data_frame()
result_df_designs = pd.DataFrame(result_designs)
result_df_designs = result_df_designs.sort_values("Design")

query_network_buildings = """
MATCH(n:Building)
RETURN n.building_name as Name
"""
result_network_buildings = neo_graph.query(query_network_buildings).to_data_frame()
result_df_network_building = pd.DataFrame(result_network_buildings)
result_df_network_building = result_df_network_building.sort_values("Name")


# Voor buildings.html
query_buildings = """
MATCH(n:Building)
RETURN n.building_name as Name, n.country as Country, n.city as City, n.link_building as Website
"""
result_buildings = neo_graph.query(query_buildings).to_data_frame()
result_df_buildings = pd.DataFrame(result_buildings)
result_df_buildings['Website'] = '[Link](' + result_df_buildings['Website'].astype(str) + ')'


# Voor designs.html
query_dash_designs = """
MATCH(n:Design_implementation)
RETURN n.implemented_design_strategies as Design, n.ecosystem_service1 as FirstEcosystem, 
n.ecosystem_service2 as SecondEcosystem, n.ecosystem_service3 as ThirdEcosystem
"""
result_dash_designs = neo_graph.query(query_dash_designs).to_data_frame()
result_df_dash_designs = pd.DataFrame(result_dash_designs)


query_buildings_top20 = """MATCH (n)-[r:IMPLEMENTS]->()
RETURN n.building_name as Name, count(r) AS num
ORDER BY num
DESC LIMIT 10
"""
result_buildings_top20 = neo_graph.query(query_buildings_top20).to_data_frame()


query_designs_top20 = """MATCH (n)-[r:USES]->()
RETURN n.implemented_design_strategies as Design, count(r) AS num
ORDER BY num
DESC LIMIT 20
"""
result_designs_top20 = neo_graph.query(query_designs_top20).to_data_frame()


def graph_buildings_to_designs():
    query = """
    MATCH (p:Building)-[r:IMPLEMENTS]->(m:Design_implementation)
    RETURN p, r, m
    """

    results = driver.session().run(query)

    G = nx.MultiDiGraph()

    nodes = list(results.graph()._nodes.values())

    node_idlist = {}
    for node in nodes:
        try:
            node_idlist[node.id] = ["Building", node._properties["building_name"]]
        except KeyError:
            node_idlist[node.id] = ["Design_strategy", node._properties["implemented_design_strategies"]]

    for node in nodes:
        G.add_node(node.id, labels=node._labels, properties=node._properties)

    rels = list(results.graph()._relationships.values())
    for rel in rels:
        G.add_edge(rel.start_node.id, rel.end_node.id, key=rel.id, type=rel.type, properties=rel._properties)
    return G, node_idlist


def graph_designs_to_es():
    query = """
    MATCH (p:Design_implementation)-[r:USES]->(m:Ecosystem_service)
    RETURN p, r, m
    """

    results = driver.session().run(query)

    G = nx.MultiDiGraph()

    nodes = list(results.graph()._nodes.values())

    node_idlist = {}
    for node in nodes:
        try:
            node_idlist[node.id] = ["Design_strategy", node._properties["implemented_design_strategies"]]
        except KeyError:
            node_idlist[node.id] = ["Ecosystem_service", node._properties["categories"]]

    for node in nodes:
        G.add_node(node.id, labels=node._labels, properties=node._properties)

    rels = list(results.graph()._relationships.values())
    for rel in rels:
        G.add_edge(rel.start_node.id, rel.end_node.id, key=rel.id, type=rel.type, properties=rel._properties)
    return G, node_idlist


def get_building_degree_centrality():
    G, node_idlist = graph_buildings_to_designs()

    # Get out degree centrality
    out_deg_centrality = nx.out_degree_centrality(G)

    # Delete keys that have degree of 0, i.e. delete design_implementations and keep buildings
    del_keys = []
    for key, value in out_deg_centrality.items():
        if value == 0:
            del_keys.append(key)
    for key in del_keys:
        out_deg_centrality.pop(key)

    # Keep the 10 buildings with highest degree centrality
    top10_out_deg_centrality = sorted(out_deg_centrality, key=out_deg_centrality.get, reverse=True)[:10]

    # Create list of id's and their scores
    top10_out_deg_centrality2 = []
    for item in top10_out_deg_centrality:
        temp_list = [item, out_deg_centrality[item]]
        top10_out_deg_centrality2.append(temp_list)

    # Create list of building name's and their scores
    top10_deg_buildings = []
    for item in top10_out_deg_centrality2:
        temp_list = [node_idlist[item[0]][1], round(item[1], 3)]
        top10_deg_buildings.append(temp_list)

    df_deg_buildings = pd.DataFrame(top10_deg_buildings, columns=["Name", "score"])
    df = pd.merge(df_deg_buildings, result_buildings_top20, on=["Name", "Name"])
    top10_deg_buildings_list = df.values.tolist()
    return top10_deg_buildings_list


def get_design_degree_centrality():
    G, node_idlist = graph_designs_to_es()

    # Get out degree centrality
    out_deg_centrality = nx.out_degree_centrality(G)

    # Delete keys that have degree of 0, i.e. delete ecosystem_services and keep design_implementations
    del_keys = []
    for key, value in out_deg_centrality.items():
        if value == 0:
            del_keys.append(key)
    for key in del_keys:
        out_deg_centrality.pop(key)

    # Keep the 10 designs with highest degree centrality
    top10_out_deg_centrality = sorted(out_deg_centrality, key=out_deg_centrality.get, reverse=True)[:10]

    # Create list of id's and their scores
    top10_out_deg_centrality2 = []
    for item in top10_out_deg_centrality:
        temp_list = [item, out_deg_centrality[item]]
        top10_out_deg_centrality2.append(temp_list)

    # Create list of designs and their scores
    top10_deg_designs = []
    for item in top10_out_deg_centrality2:
        temp_list = [node_idlist[item[0]][1], round(item[1], 3)]
        top10_deg_designs.append(temp_list)

    df_deg_designs = pd.DataFrame(top10_deg_designs, columns=["Design", "score"])
    df = pd.merge(df_deg_designs, result_designs_top20, on=["Design", "Design"])
    top10_deg_designs_list = df.values.tolist()
    return top10_deg_designs_list


def get_design_closeness_centrality():
    G, node_idlist = graph_buildings_to_designs()

    # Get closeness centrality
    close_centrality = nx.closeness_centrality(G)

    # Delete keys that have closeness of 0
    del_keys = []
    for key, value in close_centrality.items():
        if value == 0:
            del_keys.append(key)
    for key in del_keys:
        close_centrality.pop(key)

    # Keep the 10 buildings with highest closeness centrality
    top10_close_centrality = sorted(close_centrality, key=close_centrality.get, reverse=True)[:10]

    # Create list of id's and their scores
    top10_close_centrality2 = []
    for item in top10_close_centrality:
        temp_list = [item, close_centrality[item]]
        top10_close_centrality2.append(temp_list)

    # Create list of designs and their scores
    top10_closeness_designs = []
    for item in top10_close_centrality2:
        temp_list = [node_idlist[item[0]][1], round(item[1], 3)]
        top10_closeness_designs.append(temp_list)
    return top10_closeness_designs


def get_design_eigenvector():
    G, node_idlist = graph_buildings_to_designs()

    # Get out degree centrality
    eigenvector_centrality = nx.eigenvector_centrality_numpy(G)

    # Delete keys that have degree of 0, i.e. delete design_implementations and keep buildings
    del_keys = []
    for key, value in eigenvector_centrality.items():
        if value == 0:
            del_keys.append(key)
    for key in del_keys:
        eigenvector_centrality.pop(key)

    # Keep the 10 buildings with highest degree centrality
    top10_eigenvector_centrality = sorted(eigenvector_centrality, key=eigenvector_centrality.get, reverse=True)[:10]

    # Create list of id's and their scores
    top10_eigenvector_centrality2 = []
    for item in top10_eigenvector_centrality:
        temp_list = [item, eigenvector_centrality[item]]
        top10_eigenvector_centrality2.append(temp_list)

    # Create list of building name's and their scores
    top10_eigenvector_designs = []
    for item in top10_eigenvector_centrality2:
        temp_list = [node_idlist[item[0]][1], round(item[1], 3)]
        top10_eigenvector_designs.append(temp_list)
    return top10_eigenvector_designs


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        # DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/')
    @app.route('/index')
    def home():
        return render_template("index.html")

    @app.route("/buildings_network")
    def network():
        return render_template('/buildings_network.html', Buildings=result_df_network_building["Name"], url=url_graph, password=password)

    @app.route("/background_process")
    def background_process():
        try:
            select = request.args.get('dropdown')
            country = result_df_buildings.loc[result_df_buildings['Name'] == str(select), 'Country'].item()
            city = result_df_buildings.loc[result_df_buildings['Name'] == str(select), 'City'].item()
            result = [str(country) + ", " + str(city)]
            return jsonify(result=result)
        except Exception as e:
            return str(e)

    @app.route("/designs_network")
    def designs_network():
        return render_template('/designs_network.html', Designs=result_df_designs["Design"], url=url_graph, password=password)

    @app.route("/background_process2")
    def background_process2():
        pass

    dash_app = Dash(__name__, server=app, routes_pathname_prefix='/dash_buildings/')
    dash_app.layout = html.Div([
        dash_table.DataTable(
            id='datatable-interactivity',
            data=result_df_buildings.to_dict('records'),
            columns=[{'id': x, 'name': x, 'presentation': 'markdown'} if x == 'Website' else {'id': x, 'name': x} for x
                     in result_df_buildings.columns],
            filter_action="native",
            sort_action="native",
            page_action="native",
            page_current=0,
            page_size=6,
            fixed_rows={'headers': True},
            virtualization=True,
            style_table={
                'height': '400px',
                'overflowY': 'auto'
            },
            style_cell={
                'minWidth': 95,
                'maxWidth': 95,
                'width': 95,
                'textAlign': 'left',
                'padding': '5px'
            },
            style_as_list_view=True,  # Removes verticle lines
            style_header={
                'backgroundColor': 'white',
                'fontWeight': 'bold',
                'font-family': 'Helvetica Neue',
                'fontSize': 'small'
            },
            style_data={
                'font-family': 'Helvetica Neue',
                'fontSize': 'small',
                'whiteSpace': 'normal',
                'height': 'auto'
            },
            css=[
                {"selector": ".dash-spreadsheet tr th", "rule": "height: 15px;"},  # set height of header
                {"selector": ".dash-spreadsheet tr td", "rule": "height: 1px;"},  # set height of body rows
            ]
        ),
        html.Div(id='datatable-interactivity-container')
    ])

    @app.route("/buildings")
    def buildings():
        return render_template('/buildings.html', lst_top10=get_building_degree_centrality())

    dash_app = Dash(__name__, server=app, routes_pathname_prefix='/dash_design/')
    dash_app.layout = html.Div([
        dash_table.DataTable(
            id='datatable-interactivity',
            data=result_df_dash_designs.to_dict('records'),
            columns=[
                {"name": i, "id": i} for i in result_df_dash_designs.columns
            ],
            filter_action="native",
            sort_action="native",
            page_action="native",
            page_current=0,
            page_size=10,
            fixed_rows={'headers': True},
            virtualization=True,
            style_table={
                'height': '400px',
                'overflowY': 'auto'
            },
            style_cell={
                'minWidth': 95,
                'maxWidth': 95,
                'width': 95,
                'textAlign': 'left',
                'padding': '5px'
            },
            style_as_list_view=True,  # Removes verticle lines
            style_header={
                'backgroundColor': 'white',
                'fontWeight': 'bold',
                'font-family': 'Helvetica Neue',
                'fontSize': 'small'
            },
            style_data={
                'font-family': 'Helvetica Neue',
                'fontSize': 'small',
                'whiteSpace': 'normal',
                'height': 'auto'
            },
            css=[
                {"selector": ".dash-spreadsheet tr th", "rule": "height: 15px;"},  # set height of header
                {"selector": ".dash-spreadsheet tr td", "rule": "height: 1px;"},  # set height of body rows
            ]
        ),
        html.Div(id='datatable-interactivity-container')
    ])

    @app.route("/designs")
    def designs():
        return render_template('/designs.html', lst_top10=get_design_degree_centrality(),
                               lst_top10_closeness=get_design_closeness_centrality(),
                               lst_top10_eigenvector=get_design_eigenvector())

    @app.route("/about")
    def about():
        return render_template('/about.html')


    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template('/error_page.html')

    return app
