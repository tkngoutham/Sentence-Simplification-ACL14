#!/usr/bin/env python
#===================================================================================
#title           : boxer_graph_module.py                                           =
#description     : Define boxer graph class                                        =
#author          : Shashi Narayan, shashi.narayan(at){ed.ac.uk,loria.fr,gmail.com})=                                    
#date            : Created in 2014, Later revised in April 2016.                   =
#version         : 0.1                                                             =
#===================================================================================

import itertools
import math
import xml.etree.ElementTree as ET

class Boxer_Graph:
    def __init__(self):
        '''
        self.nodes[symbol] = {"positions":[], "predicates":[(predsym, locations)]}
        self.relations[symbol] = {"positions":[], "predicates":""}
        self.edges = [(par, dep, lab)]
        '''
        self.nodes = {}  
        self.relations = {} 
        self.edges = [] 
        
    def isEmpty(self):
        if len(self.nodes) == 0:
            return True
        else:
            return False

    def get_nodeset(self):
        nodeset = self.nodes.keys()
        nodeset.sort()
        return nodeset

    # @@@@@@@@@@@@@@@@@@@@@ Features extractor : Supporter functions @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    def extract_oodword(self, oodnode, main_sent_dict):
        # always just one position there
        position = self.nodes[oodnode]["positions"][0]
        oodnode_word = main_sent_dict[position][0]
        return oodnode_word

    def extract_relword(self, relnode, main_sent_dict):
        positions =  self.relations[relnode]["positions"]
        unique_pos = list(set(positions))
        
        if len(unique_pos) == 0: # nn relation
            # extract nodeset from child
            depnode = -1
            for edge in self.edges:
                if edge[2] == relnode:
                    depnode = edge[1]
            if depnode == -1:
                return nodeset
            else:
                subgraph_nodeset = self.extract_subgraph_nodeset([depnode], [])
                unique_pos = self.extract_sentence_positions(subgraph_nodeset)
        
        words = [main_sent_dict[pos][0] for pos in unique_pos if pos in main_sent_dict]
        rel_string = " ".join(words)
        return rel_string

    def extract_relation_phrase(self, relnode, nodeset, main_sent_dict, filtered_mod_pos):
        relation_span = self.extract_span_for_nodeset_with_rel(relnode, nodeset)
        unique_pos = list(set(relation_span))
        unique_valid_pos = [item for item in unique_pos if item not in filtered_mod_pos]
        unique_valid_pos.sort()
        
        words = [main_sent_dict[pos][0] for pos in unique_valid_pos if pos in main_sent_dict]
        rel_phrase = " ".join(words)
        return rel_phrase

    def calculate_iLength(self, parent_sentence, child_sentence_list):
        # Counts are done at the word level, split criteria
        lenth_complex = len(parent_sentence.split())
        
        avg_simple_sentlen = 0
        for sent in child_sentence_list:
            avg_simple_sentlen += len(sent.split())
        avg_simple_sentlen = float(avg_simple_sentlen)/len(child_sentence_list)
        iLength = int(math.ceil(lenth_complex/avg_simple_sentlen))
        return iLength
    
    def get_pattern_4_split_candidate(self, split_tuple):
        pattern_list = []
        for node in split_tuple:
            rel_pattern = []
            for edge in self.edges:
                if edge[0] == node:
                    relnode = edge[2]
                    relpred = self.relations[relnode]["predicates"]
                    rel_pattern.append(relpred)
            rel_pattern.sort()
            pattern_list.append(rel_pattern)
        pattern_list.sort() 
        pattern = ""
        for item in pattern_list:
            if len(item) == 0:
                    pattern += "NULL_"
            else:
                pattern += ("-".join(item)+"_")
        pattern = pattern[:-1]
        return pattern

    # @@@@@@@@@@@@@@@@@@@@@ Candidates extractor @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    def extract_split_candidate_tuples(self, nodeset, MAX_SPLIT_PAIR_SIZE):
        # Get Event nodes which are parent and distinct
        parent_event_nodes = []
        # Extract all children nodes 
        children_nodes = [edge[1] for edge in self.edges]
        for node in nodeset:
            preds = [item[0] for item in self.nodes[node]["predicates"]]
            if "event" in preds:
                # Check for parent nodes
                if node not in children_nodes:
                    # Have at least one of agent, theme, eq or patient as their dependent relations
                    rel_pattern = []
                    for edge in self.edges:
                        if edge[0] == node:
                            relnode = edge[2]
                            relpred = self.relations[relnode]["predicates"]
                            rel_pattern.append(relpred)
                    if ("agent" in rel_pattern) or ("theme" in rel_pattern) or ("eq" in rel_pattern) or ("patient" in rel_pattern):
                        parent_event_nodes.append(node)

        parent_distinct_event_nodes_span = []   
        # Remove Homomorphic pairs
        for node in parent_event_nodes:
            subgraph_nodeset = self.extract_subgraph_nodeset([node], [])
            subgraph_nodeset_filtered = [item for item in subgraph_nodeset if item in nodeset]
            span = self.extract_span_for_nodeset(subgraph_nodeset_filtered)
            flag = False
            for tnode_span in parent_distinct_event_nodes_span:
                if span == tnode_span[1]:
                    flag = True
                    break
            if flag == False:
                parent_distinct_event_nodes_span.append((node, span))
        parent_distinct_event_nodes = [item[0] for item in parent_distinct_event_nodes_span]
        parent_distinct_event_nodes.sort() 

        split_candidate_tuples = []
        for splitsize in range(2,MAX_SPLIT_PAIR_SIZE+1):
            split_candidate_tuples += list(itertools.combinations(parent_distinct_event_nodes, splitsize))
        return split_candidate_tuples

    def extract_drop_rel_candidates(self, nodeset, RESTRICTED_DROP_REL, processed_relnode):
        # potential edges
        potential_edges = []
        for edge in self.edges:
            parentnode = edge[0]
            depnode = edge[1]
            if (parentnode in nodeset) and (depnode in nodeset):
                potential_edges.append(edge)
        # Extract all children nodes 
        children_nodes = [edge[1] for edge in potential_edges]
        # Select all parents in the nodeset
        nodeset_to_process = []
        depthset_to_process = []
        for node in nodeset:
            # Check for parent nodes
            if node not in children_nodes:
                nodeset_to_process.append(node)
                depthset_to_process.append(0)
        # Find relation nodes with their depth
        relation_depth = self.extract_relationnode_depth(nodeset_to_process, depthset_to_process, [], [], potential_edges)
        # Sort them based on their bottom-up appearance, try to drop smaller one first. (edit distance prefers to drop longer one, so try smaller one first)
        relation_depth.sort(reverse=True)

        # Filtering out RESTRICTED_DROP_REL and processed_relnode
        relcand_set = []
        for item in relation_depth:
            relnode = item[1]
            relpred = self.relations[relnode]["predicates"]
            if (relpred not in RESTRICTED_DROP_REL) and (relnode not in processed_relnode):
                relcand_set.append(relnode)

        # Removing relnodes whose dependents are connected by non-dropable nodes
        relcand_set_filtered = []
        for relnode in relcand_set:
            # Find dependent nodeset
            dep_node = -1
            for edge in potential_edges:
                if edge[2] == relnode:
                    dep_node = edge[1]

            subgraph_nodeset = self.extract_subgraph_nodeset([dep_node], [])
            subgraph_nodeset_filtered = [item for item in subgraph_nodeset if item in nodeset]
            edges_connecting_subgraph_nodeset = self.extract_edges_super_subgraph(nodeset, subgraph_nodeset_filtered)
            
            flag = True
            for edge in edges_connecting_subgraph_nodeset:
                if self.relations[edge[2]]["predicates"] in RESTRICTED_DROP_REL:
                    flag = False
                    break
            if flag == True:
                relcand_set_filtered.append(relnode)

        # removing homomorphic relations
        relcand_span_uniq = []
        for relcand in relcand_set_filtered:
            relcand_span = self.extract_span_for_nodeset_with_rel(relcand, nodeset)
            flag = False
            for trelcand_span_tuple in relcand_span_uniq:
                if relcand_span == trelcand_span_tuple[1]:
                    flag = True
                    break
            if flag == False:
                relcand_span_uniq.append((relcand, relcand_span))
                
        relcand_uniq = [item[0] for item in relcand_span_uniq]
        return relcand_uniq

    def extract_drop_mod_candidates(self, nodeset, main_sent_dict, ALLOWED_DROP_MOD, processed_mod_pos):
        modcand_set = []
        
        local_processed_mod_pos = [] # two homomorphic node can have same postions, just consider one

        for node in nodeset:
            positions = self.nodes[node]["positions"]
            for position in positions:
                if (position not in processed_mod_pos) and (position not in local_processed_mod_pos):
                    if main_sent_dict[position][1] in ALLOWED_DROP_MOD:
                        modcand_set.append((position, node))
                        local_processed_mod_pos.append(position)
                        #print main_sent_dict[position]
        return modcand_set

    def extract_ood_candidates(self, nodeset, processed_oodnodes):
        oodnode_set = [itemnode_name for itemnode_name in nodeset if itemnode_name.startswith("OOD") and itemnode_name not in processed_oodnodes]
        oodnode_set.sort()
        return oodnode_set

    # @@@@@@@@@@@@@@@@@@@@@ Boxer Graph Processing Functions @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    
    def extract_relationnode_depth(self, nodeset_to_process, depthset_to_process, relation_depth, nodes_processed, edges):
        if len(nodeset_to_process) == 0:
            return relation_depth

        node = nodeset_to_process[0]
        depth = depthset_to_process[0]
        nodes_processed.append(node)

        for edge in edges:
            parent = edge[0]
            dependent = edge[1]
            relnode = edge[2]
            if parent == node:
                relation_depth.append((depth, relnode))
                if (dependent not in nodeset_to_process) and (dependent not in nodes_processed):
                    nodeset_to_process.append(dependent)
                    depthset_to_process.append(depth+1)
        relation_depth = self.extract_relationnode_depth(nodeset_to_process[1:], depthset_to_process[1:], relation_depth, nodes_processed, edges)
        return relation_depth

    def extract_span_for_nodeset_with_rel(self, rel_node, nodeset):
        span = self.relations[rel_node]["positions"][:]
        dep_node = -1
        for edge in self.edges:
            if edge[2] == rel_node:
                dep_node = edge[1]
        if dep_node != -1:
            subgraph_nodeset = self.extract_subgraph_nodeset([dep_node], [])
            subgraph_nodeset_filtered = [item for item in subgraph_nodeset if item in nodeset]
            span += self.extract_span_for_nodeset(subgraph_nodeset_filtered)
        unique_pos = list(set(span))
        unique_pos.sort()
        return unique_pos

    def extract_span_for_nodeset(self, nodeset):
        span = []
        for node in nodeset:
            positions = self.nodes[node]["positions"]
            span += positions
        for edge in self.edges:
            rel = edge[2]
            parnode = edge[0]
            depnode = edge[1]
            if (parnode in nodeset) and (depnode in nodeset):
                positions = self.relations[rel]["positions"]
                span += positions
        unique_pos = list(set(span))
        unique_pos.sort()
        return unique_pos

    def extract_parent_subgraph_nodeset_dict(self):
        # Calculate parents
        parents_subgraph_nodeset_dict = {}
        # Extract all children nodes 
        children_nodes = [edge[1] for edge in self.edges]
        for node in self.nodes:
            # Check for parent nodes
            if node not in children_nodes:
                parent_node = node
                subgraph_nodeset = self.extract_subgraph_nodeset([parent_node], [])
                parents_subgraph_nodeset_dict[parent_node] = subgraph_nodeset
        return parents_subgraph_nodeset_dict

    def extract_subgraph_nodeset(self, node_2_process_set, subgraph_nodeset):
        if len(node_2_process_set) == 0:
            return subgraph_nodeset
        else:
            nodename = node_2_process_set[0]
            subgraph_nodeset.append(nodename)
            for edge in self.edges:
                if edge[0] == nodename:
                    depnode = edge[1]
                    if (depnode not in node_2_process_set) and (depnode not in subgraph_nodeset):
                        node_2_process_set.append(depnode)
            subgraph_nodeset =  self.extract_subgraph_nodeset(node_2_process_set[1:], subgraph_nodeset)
            return subgraph_nodeset

    def extract_main_sentence(self, nodeset, main_sent_dict, filtered_mod_pos):
        span = []
        for node in nodeset:
            positions = self.nodes[node]["positions"]
            span += positions
        for edge in self.edges:
            rel = edge[2]
            parnode = edge[0]
            depnode = edge[1]
            if (parnode in nodeset) and (depnode in nodeset):
                positions = self.relations[rel]["positions"]
                span += positions
        unique_pos = list(set(span))
        unique_valid_pos = [item for item in unique_pos if item not in filtered_mod_pos]
        unique_valid_pos.sort()
        
        words = [main_sent_dict[pos][0] for pos in unique_valid_pos if pos in main_sent_dict]
        main_sentence = " ".join(words)
        return main_sentence

    def extract_span_min_max(self, nodeset):
        span = []
        for node in nodeset:
            positions = self.nodes[node]["positions"]
            span += positions
        for edge in self.edges:
            rel = edge[2]
            parnode = edge[0]
            depnode = edge[1]
            if (parnode in nodeset) and (depnode in nodeset):
                positions = self.relations[rel]["positions"]
                span += positions
        unique_pos = list(set(span))
        unique_pos.sort()
        
        if len(unique_pos) == 0:
            return (-1, -1)
        else:
            return (unique_pos[0], unique_pos[-1])    

    def extract_sentence_positions(self, nodeset):
        span = []
        for node in nodeset:
            positions = self.nodes[node]["positions"]
            span += positions
        for edge in self.edges:
            rel = edge[2]
            parnode = edge[0]
            depnode = edge[1]
            if (parnode in nodeset) and (depnode in nodeset):
                positions = self.relations[rel]["positions"]
                span += positions
        unique_pos = list(set(span))
        return unique_pos

    def extract_edges_super_subgraph(self, super_nodeset, sub_nodeset):
        connecting_edges = []
        for edge in self.edges:
            rel = edge[2]
            parnode = edge[0]
            depnode = edge[1]
            if (parnode in super_nodeset) and (parnode not in sub_nodeset) and (depnode in super_nodeset) and (depnode in sub_nodeset):
                connecting_edges.append(edge)
        return connecting_edges

    # @@@@@@@@@@@@@@@@@@@@@@ Node set changing operations @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    
    def partition_drs_for_successful_candidate(self, split_candidate, parent_subgraph_nodeset_dict):
        node_subgraph_nodeset_dict = {}
        node_span_dict = {}        
        for node in split_candidate:
            node_subgraph_nodeset_dict[node] = parent_subgraph_nodeset_dict[node][:]
            node_span_dict[node] = self.extract_span_min_max(parent_subgraph_nodeset_dict[node])
        # print "node_span_dict : "+str(node_span_dict)

        # Normal nodes attachment with their increasing span
        span_normalnodes = [(self.extract_span_min_max(parent_subgraph_nodeset_dict[nodename]) , nodename) 
                            for nodename in parent_subgraph_nodeset_dict if nodename.startswith("x") and nodename not in split_candidate]
        span_normalnodes.sort()
        for item in span_normalnodes:
            span_subgraph = item[0]
            parent_subgraph = item[1]
            self.attach_a_subgraph(node_subgraph_nodeset_dict, node_span_dict, parent_subgraph, span_subgraph, parent_subgraph_nodeset_dict)

        # Extra nodes attachment with their increasing span and 
        span_extranodes = [(self.extract_span_min_max(parent_subgraph_nodeset_dict[nodename]) , nodename) 
                           for nodename in parent_subgraph_nodeset_dict if nodename.startswith("E") and nodename not in split_candidate]
        span_extranodes.sort()
        for item in span_extranodes:
            span_subgraph = item[0]
            parent_subgraph = item[1]
            self.attach_a_subgraph(node_subgraph_nodeset_dict, node_span_dict, parent_subgraph, span_subgraph, parent_subgraph_nodeset_dict)

        # OOD (out of discourse) nodes attachment with their increasing span
        span_oodnodes = [(self.extract_span_min_max(parent_subgraph_nodeset_dict[nodename]) , nodename) 
                         for nodename in parent_subgraph_nodeset_dict if nodename.startswith("OOD") and nodename not in split_candidate]
        span_oodnodes.sort()
        for item in span_oodnodes:
            span_subgraph = item[0]
            parent_subgraph = item[1]
            self.attach_a_subgraph(node_subgraph_nodeset_dict, node_span_dict, parent_subgraph, span_subgraph, parent_subgraph_nodeset_dict)

        return node_subgraph_nodeset_dict, node_span_dict
    
    def attach_a_subgraph(self, node_subgraph_nodeset_dict, node_span_dict, parent_subgraph, span_subgraph, parent_subgraph_nodeset_dict):
        # Finding closest node to attach to
        mean_subgraph = float(span_subgraph[0]+span_subgraph[1])/2
        mean_nodes = [(float(node_span_dict[node][0]+node_span_dict[node][1])/2, node) for node in node_span_dict]
        distance_from_nodes = [(abs(item[0]-mean_subgraph), item[1]) for item in mean_nodes]
        distance_from_nodes.sort()
        required_node = distance_from_nodes[0][1]

        # Updating nodeset and span
        node_subgraph_nodeset_dict[required_node] = list(set(node_subgraph_nodeset_dict[required_node]+parent_subgraph_nodeset_dict[parent_subgraph]))
        node_span_dict[required_node] = self.extract_span_min_max(node_subgraph_nodeset_dict[required_node])     

    def drop_relation(self, nodeset, relnode_to_process, filtered_mod_pos):
        nodeset_to_drop = []
        filtered_mod_pos_new = filtered_mod_pos[:]
        
        depnode = -1
        for edge in self.edges:
            if edge[2] == relnode_to_process:
                depnode = edge[1]
        if depnode != -1:
            subgraph_nodeset = self.extract_subgraph_nodeset([depnode], [])
            nodeset_to_drop += subgraph_nodeset[:]

        # Span
        relnode_span = self.extract_span_for_nodeset_with_rel(relnode_to_process, nodeset)

        # filtering out positions
        filtered_mod_pos_new += relnode_span[:]
        filtered_mod_pos_final = list(set(filtered_mod_pos_new))
        filtered_mod_pos_final.sort()

        # Drop all homomorphic relations and 
        for edge in self.edges:
            trelnode = edge[2]
            parent = edge[0]
            dependent = edge[1]
            if (trelnode != relnode_to_process) and (parent in nodeset) and  (dependent in nodeset):
                trelnode_span = self.extract_span_for_nodeset_with_rel(trelnode, nodeset)
                if trelnode_span == relnode_span:
                    # homomorphic
                    subgraph_nodeset = self.extract_subgraph_nodeset([dependent], [])
                    nodeset_to_drop += subgraph_nodeset[:]
                    
        filtered_nodeset = [node for node in nodeset if node not in nodeset_to_drop]
        filtered_nodeset.sort()

        return filtered_nodeset, filtered_mod_pos_final

    # @@@@@@@@@@@@@@@@@@@@@@ Boxer Graph -> Elementary Tree @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    def convert_to_elementarytree(self):
        # Writing Discourse Data : nodes, relations, edges
        boxer = ET.Element("box")

        nodes = ET.SubElement(boxer, "nodes")
        for node in self.nodes:
            bnode = ET.SubElement(nodes, "node")
            bnode.attrib = {"sym":node}

            # Span positions
            span = ET.SubElement(bnode, "span")
            positions = self.nodes[node]["positions"]
            positions.sort()
            for pos in positions:
                locelt = ET.SubElement(span, "loc")
                locelt.attrib = {"id":str(pos)}

            # Predicates
            predicates = self.nodes[node]["predicates"]
            predselt = ET.SubElement(bnode, "preds")
            for predtuple in predicates:
                predname = predtuple[0]
                predelt = ET.SubElement(predselt, "pred")
                predelt.attrib = {"sym":predname}
                
                predpositions = predtuple[1]
                predpositions.sort()
                for predpos in predpositions:
                    predlocelt = ET.SubElement(predelt, "loc")
                    predlocelt.attrib = {"id":str(predpos)}

        rels = ET.SubElement(boxer, "rels")
        for rel in self.relations:
            brel = ET.SubElement(rels, "rel")
            brel.attrib = {"sym":rel}

            relname = self.relations[rel]["predicates"]
            predelt = ET.SubElement(brel, "pred")
            predelt.attrib = {"sym":relname}
                
            relpositions = self.relations[rel]["positions"]
            relpositions.sort()
            span = ET.SubElement(brel, "span")
            for relpos in relpositions:
                rellocelt = ET.SubElement(span, "loc")
                rellocelt.attrib = {"id":str(relpos)}

        edges = ET.SubElement(boxer, "edges")
        for edge in self.edges:
            edgeelt = ET.SubElement(edges, "edge")
            edgeelt.attrib = {"lab":edge[2], "par":edge[0], "dep":edge[1]}
        
        return boxer

    # @@@@@@@@@@@@@@@@@@@@@@ Boxer Graph -> Dot Node @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    
    def convert_to_dotstring(self, sentid, main_sentence, main_sent_dict, simple_sentences):
        dot_string = "digraph boxer{\n"
		
        # Creating root node
        nodename = 0
        textdot_root, nodename = self.textdot_root_node(nodename, sentid, main_sentence, main_sent_dict, simple_sentences)
        dot_string += textdot_root+"\n"        
        # Creating all boxer nodes
        node_graph_dict = {}
        for node in self.nodes:
            textdot_node, nodename = self.textdot_node(nodename, node, self.nodes[node]["positions"], self.nodes[node]["predicates"])
            node_graph_dict[node] = "struct"+str(nodename)
            dot_string += textdot_node+"\n"
       	# Creating edges
        for edge in self.edges:
            reldata = edge[2]+"-"+self.relations[edge[2]]["predicates"]+"-"+str(self.relations[edge[2]]["positions"])
            par_boxergraph = node_graph_dict[edge[0]]
            dep_boxergraph = node_graph_dict[edge[1]]	 
            dot_string += par_boxergraph+" -> "+dep_boxergraph+"[label=\""+reldata+"\"];\n"

        # Extracting parents 
        parents_subgraph_nodeset_dict = self.extract_parent_subgraph_nodeset_dict()
        #print parents_subgraph_nodeset_dict

       	# Connect all parents to root
        for parent in  parents_subgraph_nodeset_dict:
            par_boxergraph = node_graph_dict[parent]
            dot_string += "struct1 -> "+par_boxergraph+";\n"
        dot_string += "}"
        return dot_string

    def textdot_root_node(self, nodename, sentid, main_sentence, main_sent_dict, simple_sentences):
        textdot_root = "struct"+str(nodename+1)+" [shape=record,label=\"{"
        textdot_root += "sentId: "+sentid+"|"
        textdot_root += self.processtext("main: "+main_sentence)+"|"
        for simple_sent in simple_sentences:
            textdot_root += self.processtext("simple: "+simple_sent)+"|"
			
        main_sent_dict_text = ""
        positions = main_sent_dict.keys()
        positions.sort()
        for pos in positions:
            main_sent_dict_text += str(pos)+":("+main_sent_dict[pos][0]+","+main_sent_dict[pos][1]+") "
        textdot_root += self.processtext(main_sent_dict_text)
        textdot_root += "}\"];"
        return textdot_root, nodename+1
			
    def textdot_node(self, nodename, node, positions, predicates):
        textdot_node = "struct"+str(nodename+1)+" [shape=record,label=\"{"
        textdot_node += "node: "+node+"|"
        textdot_node += self.processtext(str(positions))+"|"
        index = 0
        for predicate_info in predicates:
            textdot_node += predicate_info[0]+" "+self.processtext(str(predicate_info[1]))
            index += 1
            if index < len(predicates):
                textdot_node += "|" 
        textdot_node += "}\"];"
        return textdot_node, nodename+1

    def processtext(self, inputstring):
        linesize = 100
        outputstring = ""
        index = 0
        substr = inputstring[index*linesize:(index+1)*linesize]
        while (substr!=""):
            outputstring += substr
            index += 1
            substr = inputstring[index*linesize:(index+1)*linesize]
            if substr!="":
                outputstring += "\\n"
        return outputstring

    # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ Done @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
