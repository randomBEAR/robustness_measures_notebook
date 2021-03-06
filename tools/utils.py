import networkx as nx
import collections as ct
import glob
import json
import os


def load_graph_list(path):
    """
    Load a bunch of graphs from a given directory according to networkx specifications.
    :param path: path where graph data is stored
    :return: a list of graphs
    """
    os.chdir(path)
    graph_list = list()
    for file in glob.glob("*.json"):
        with open(file) as f:
            json_graph = json.load(f)
            graph = parse_graph_from_json(json_graph)
            clean_isolated_nodes(graph)
            graph = fix_connectivity(graph)
            graph_list.append(graph)
    return graph_list


def build_presence_dictionary(betweenness_centrality_lists, top_number):
    """
    Builds a presence list that counts how many time a node appears in the top 15 nodes depending on the
    score of the betweenness centrality.
    :param betweenness_centrality_lists:  a dictionary containing all the bc values for each snapshot
    :param top_number: the number of nodes we want to see in the gantt chart
    :return: a dictionary of list
    """
    number_of_snapshot = len(betweenness_centrality_lists)

    # Sort each snapshot, select the best top_number nodes.
    sorted_snapshots = [None] * number_of_snapshot
    presence_count = ct.defaultdict(list)
    for i in range(number_of_snapshot):
        sorted_snapshots[i] = sorted(betweenness_centrality_lists[i].items(), key=lambda x: x[1], reverse=True)
        top_list = [sorted_snapshots[i][j] for j in range(top_number)]
        for item in top_list:
            presence_count[item[0]].append(i)
    return presence_count


def get_betweenness_top_nodes(betweenness_centrality_lists):
    """
    Return only the keys of the top nodes sorted by betweenness centrality
    :param betweenness_centrality_lists: a dictionary containing all the bc values for each snapshot
    :return: a list of nodes
    """
    return build_presence_dictionary(betweenness_centrality_lists, top_number=15).keys()


def removes_satellites(graph):
    """
    Recursive function, removes from the graph every satellite recursively until all the satellites are removed.
    :param graph: a networkx graph
    :return: the number of nodes removed
    """
    nodes_removed = 0
    for node in list(graph.nodes):
        if nx.degree(graph, node) == 1:
            nodes_removed += 1
            graph.remove_node(node)
    if nodes_removed == 0:
        return 0
    else:
        return nodes_removed + removes_satellites(graph)


def betweenness_centrality_intersection(bc_list):
    """
    Computes the intersection between the dictionaries  of the betweenness centrality and returns it
    :param bc_list: list of betweenness centrality dictionaries
    :return: a the same list where all the nodes outside the intersection are removed
    """
    keys_a = bc_list[0].keys()
    for bc in bc_list:
        keys_b = bc.keys()
        keys_a = keys_a & keys_b

    for i in range(len(bc_list)):
        keys_list = list(bc_list[i].keys())
        for key in keys_list:
            if key not in keys_a:
                del bc_list[i][key]


def read_k_conn_from_files(path):
    """
    Returns the list of k-vertex connectivity results previously calculated
    and stored in json files.
    :param path: folder in which files are
    :return: the lsit of k-vertex connectivity results
    """
    os.chdir(path)
    snapshot_list = [None] * len(glob.glob('*.json'))
    for i, file in enumerate(glob.glob('*.json')):
        with open(file) as f:
            snapshot_list[i] = json.load(f)
    return snapshot_list


def important_nodes(graph):
    """
    Returns the most important nodes
    according to betweenness centrality result
    :param graph: a networkx graph
    :return: a subgraph of the most important nodes and the betweenness centrality values
    """
    betweenness_centrality = nx.betweenness_centrality(graph)
    betweenness_sorted = sorted(betweenness_centrality.items(), key=lambda x: x[1])
    betweenness_values = [x[1] for x in betweenness_sorted]
    betweenness_mean = sum(betweenness_values) / len(betweenness_values)
    subgraph = graph.copy()
    threshold = 3 * betweenness_mean
    for v, k in betweenness_sorted:
        if k < threshold:
            subgraph.remove_node(v)
    return subgraph, betweenness_centrality


def clean_isolated_nodes(graph):
    """
    Removes nodes without edges from the graph
    :param graph: a networkx graph
    :return:
    """
    graph.remove_nodes_from(list(nx.isolates(graph)))


def fix_connectivity(graph):
    """
    Select the largest connected subgraph among the set of connected subgraph.
    :param graph: a networkx graph
    :return: the largest subgraph
    """
    connected = nx.is_connected(graph)
    if not connected:
        # Cut out the largest set of connected components and return it as a subgraph
        return max(nx.connected_component_subgraphs(graph), key=len)


def parse_graph_from_json(json_graph):
    """
    Converts the Lightning Network JSON representation to a networkx representation.
    :param json_graph: a JSON file
    :return: a networkx undirected graph
    """
    graph = nx.Graph()

    # Add each node in the graph
    for node in json_graph['nodes']:
        graph.add_node(node['pub_key'], last_update=node['last_update'])

    # Add each edge in the graph
    # Some edges are missing the node1 and node2 policy fields,
    # so a check is needed before processing it
    for edge in json_graph['edges']:
        if edge['node1_policy'] is not None and \
                edge['node2_policy'] is not None:
            graph.add_edge(edge['node1_pub'],
                           edge['node2_pub'],
                           capacity=int(edge['capacity']),
                           # weight=int(edge['capacity']),
                           last_update=int(edge['last_update']),
                           channel_id=edge['channel_id'],
                           chan_point=edge['chan_point'],
                           node1_timelock_delta=int(edge['node1_policy']['time_lock_delta']),
                           node1_min_htlc=int(edge['node1_policy']['min_htlc']),
                           node1_fee_base_msat=int(edge['node1_policy']['fee_base_msat']),
                           node1_fee_rate_milli_msat=int(edge['node1_policy']['fee_rate_milli_msat']),
                           node2_timelock_delta=int(edge['node2_policy']['time_lock_delta']),
                           node2_min_htlc=int(edge['node2_policy']['min_htlc']),
                           node2_fee_base_msat=int(edge['node2_policy']['fee_base_msat']),
                           node2_fee_rate_milli_msat=int(edge['node2_policy']['fee_rate_milli_msat'])
                           )
    return graph


def core_component(graph_list):
    """
    Returns the list of nodes that never disconnected from the network.
    :param graph_list: a list of networkx graphs
    :return: a graph that is the intersection of all the graph in the list
    """
    if not graph_list:
        return []
    result = set(graph_list[0].nodes)
    for graph in graph_list:
        result = set(graph.nodes) & result
    return result


def overall_balance(graph):
    """
    Returns the amount of bitcoins currently used in the graph.
    :param graph: a networkx graph
    :return: the aggregated capacities of the graph
    """
    network_capacity = 0
    for item in nx.get_edge_attributes(graph, 'capacity').values():
        network_capacity += item
    return network_capacity
