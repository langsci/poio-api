# -*- coding: utf-8 -*-
#
# Poio Tools for Linguists
#
# Copyright (C) 2009-2013 Poio Project
# Author: António Lopes <alopes@cidles.eu>
# URL: <http://media.cidles.eu/poio/>
# For license information, see LICENSE.TXT

"""This module contains classes to access Elan data.
The class Eaf is a low level API to .eaf files.

EafGlossTree, EafPosTree, etc. are the classes to
access the data via tree, which also contains the
original .eaf IDs. Because of this EafTrees are
read-/writeable.
"""

from __future__ import absolute_import

import re

from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.etree.ElementTree as ET

import poioapi.io.graf

from graf import Graph
from graf import Node, Edge
from graf import Annotation, AnnotationSpace
from graf import Region

class Parser(poioapi.io.graf.BaseParser):
    """
    Class that will handle parse Elan files.

    """

    def __init__(self, filepath, data_structure_hierarchy=None):
        """Class's constructor.

        Parameters
        ----------
        filepath : str
            Path of the elan file.
        data_structure_hierarchy : object
            This object contains the data hierarchy and the constraints.

        """

        self.filepath = filepath

        self.data_structure_hierarchy = data_structure_hierarchy
        self.data_structure_constraints = dict()

    def as_graf(self):

        self.graph = Graph()

        self.tree = ET.parse(self.filepath).getroot()

        self.tiers = self.tree.findall('TIER')
        root_tiers = self.get_root_tiers(self.tiers)

        self.regions_map = self.get_regions()

        for root_tier in root_tiers:
            self._parent_tier_id = None
            self._parent_linguistic_type_ref = None
            self._tier_id = root_tier.attrib['TIER_ID']
            self._linguistic_type_ref = root_tier.attrib['LINGUISTIC_TYPE_REF'].\
            replace(" ","_")

            root_annotations = self.get_annotations_for_tier(root_tier)
            self.add_graf_annotations(root_annotations)

            self._add_data_constraint(self._tier_id, self._linguistic_type_ref)

            self.find_children_tiers_for_tier(root_tier)

        return self.graph

    def get_root_tiers(self, tiers=None):

        root_tiers = []

        for tier in tiers:
            if not 'PARENT_REF' in tier.attrib:
                root_tiers.append(tier)

        return root_tiers

    def get_child_tiers_for_tier(self, tier):

        tier_id = tier.attrib['TIER_ID']

        tier_childs = self.tree.findall("TIER[@PARENT_REF='"+tier_id+"']")

        return tier_childs

    def find_children_tiers_for_tier(self, tier):

        children = self.get_child_tiers_for_tier(tier)

        for child in children:
            annotations = self.get_annotations_for_tier(child)

            self._parent_tier_id = tier.attrib['TIER_ID']
            self._parent_linguistic_type_ref = tier.attrib['LINGUISTIC_TYPE_REF'].\
            replace(" ","_")

            self._tier_id = child.attrib['TIER_ID']
            self._linguistic_type_ref = child.attrib['LINGUISTIC_TYPE_REF'].\
            replace(" ","_")

            self.add_graf_annotations(annotations)

            self._add_data_constraint(self._tier_id, self._linguistic_type_ref)

            child_children = self.get_child_tiers_for_tier(child)

            if len(child_children) > 0:
                self.find_children_tiers_for_tier(child)

    def _add_data_constraint(self, tier_id, linguistic_type_ref):

        if linguistic_type_ref in self.data_structure_constraints:
            self.data_structure_constraints[linguistic_type_ref].append(tier_id)
        else:
            self.data_structure_constraints[linguistic_type_ref] = [tier_id]

    def get_annotations_for_tier(self, tier, annotation_parent=None):

        tier_annotations = tier.findall("ANNOTATION")

        return tier_annotations

    def add_graf_annotations(self, annotations):

        prefix_name = self._linguistic_type_ref+"/"+self._tier_id
        annotation_name = self._linguistic_type_ref
        parent_ref = self._parent_linguistic_type_ref

        graf_xml_writer = poioapi.io.graf.Writer()

        if annotation_name not in self.graph.additional_information:
            element_tree = graf_xml_writer.create_xml_graph_header(annotation_name,
                parent_ref)
        else:
            element_tree = self.graph.additional_information[annotation_name]

        for annotation in annotations:
            annotation_elements = annotation.getiterator()

            if annotation_elements[1].tag == 'ALIGNABLE_ANNOTATION':
                annotation_id = annotation_elements[1].attrib['ANNOTATION_ID']
                annotation_value = annotation_elements[1].find('ANNOTATION_VALUE').text

                features_map = {'annotation_value':annotation_value,
                                'time_slot1':annotation_elements[1].attrib['TIME_SLOT_REF1'],
                                'time_slot2':annotation_elements[1].attrib['TIME_SLOT_REF2']}

                regions = (self.regions_map[annotation_elements[1].attrib['TIME_SLOT_REF1']],
                           self.regions_map[annotation_elements[1].attrib['TIME_SLOT_REF2']])

                index = re.sub("\D", "", annotation_id)

                if parent_ref is not None:
                    from_node = self.find_from_node(parent_ref, regions)
                else:
                    from_node = None

                (node, region, edge) = self.add_graf_node(index, prefix_name, regions, from_node)

                annotation_ref = prefix_name+"/n"+index

                annotation = self.add_graf_annotation(annotation_name, annotation_id,
                    annotation_ref, features_map)

                graf_xml_writer.create_graf_xml_node(element_tree,annotation,
                    annotation_ref, node, region, regions, from_node, edge)
            else:
                annotation_id = annotation_elements[1].attrib['ANNOTATION_ID']
                annotation_value = annotation_elements[1].find('ANNOTATION_VALUE').text
                annotation_ref = annotation_elements[1].attrib['ANNOTATION_REF']

                features_map = {'annotation_value':annotation_value,
                                'ref_annotation':annotation_ref,
                                'tier_id':self._tier_id}

                for attribute in annotation_elements[1].attrib:
                    if attribute != 'ANNOTATION_REF' and attribute != 'ANNOTATION_ID' and\
                       attribute != 'ANNOTATION_VALUE':
                        features_map[attribute] = annotation_elements[1].attrib[attribute]

                index = re.sub("\D", "", annotation_ref)
                annotation_ref = self._parent_linguistic_type_ref+"/"+\
                                 self._parent_tier_id+"/n"+index

                from_node = self.graph.nodes[annotation_ref]

                index = re.sub("\D", "", annotation_id)
                (node, _, edge) = self.add_graf_node(index, prefix_name, from_node=from_node)

                annotation = self.add_graf_annotation(annotation_name, annotation_id,
                    annotation_ref, features_map)

                graf_xml_writer.create_graf_xml_node(element_tree,annotation,
                    node.id, node, from_node=from_node, edge=edge)

        self.graph.additional_information[annotation_name] = element_tree

    def find_from_node(self, parent_ref, anchors):

        for region in self.graph.regions:
            if parent_ref in region.id:
                if (int(region.anchors[0]) <= int(anchors[0]) <= int(region.anchors[1]))\
                and (int(region.anchors[0]) <= int(anchors[1]) <= int(region.anchors[1])):
                    node_id = re.sub(r"(.*)/r", r"\1/n", region.id)
                    node = self.graph.nodes[node_id]
                    return node
        return None

    def get_regions(self):

        time_order = self.tree.find('TIME_ORDER')
        time_order_dict = dict()

        for time in time_order:
            key = time.attrib['TIME_SLOT_ID']

            if 'TIME_VALUE' in time.attrib:
                value = time.attrib['TIME_VALUE']
            else:
                value = 0

            time_order_dict[key] = value

        return time_order_dict

    def add_graf_node(self, node_index, prefix_name, regions=None, from_node=None):

        node_id = prefix_name+"/n"+node_index
        node = Node(node_id)

        if from_node is not None:
            edge_id = "e"+node_index
            edge = Edge(edge_id, from_node, node)

            self.graph.edges.add(edge)
        else:
            edge = None

        if regions is not None:
            region_id = prefix_name+"/r"+node_index
            region = Region(region_id, *regions)
            node.add_region(region)

            self.graph.regions.add(region)
        else:
            region = None

        self.graph.nodes.add(node)

        return node, region, edge

    def add_graf_annotation(self, annotation_name, annotation_id,
                            annotation_ref, annotation_features=None):

        annotation = Annotation(annotation_name, annotation_features,
            annotation_id)

        self.graph.nodes[annotation_ref].annotations.add(annotation)

        annotation_space = AnnotationSpace(annotation_name)
        annotation_space.add(annotation)

        self.graph.annotation_spaces.add(annotation_space)

        return annotation

class Writer:
    """
    Class that will handle the writing of
    GrAF files into Elan files again.

    """

    def __init__(self, extinfofile, outputfile):
        """Class's constructor.

        Parameters
        ----------
        extinfofile : str
            Path of the metafile.
        outputfile : str
            Path and name of the new elan file.

        """

        self.extinfofile = extinfofile
        self.outputfile = outputfile

    def write(self):
        """This method will look into the metafile
        and then reconstruct the Elan file.

        """

        tree = ET.parse(self.extinfofile)
        root = tree.getroot()

        miscellaneous = root.findall('./file/miscellaneous/')
        element_tree = Element(miscellaneous[0].tag, miscellaneous[0].attrib)

        for element in miscellaneous:
            if element.tag != 'ANNOTATION_DOCUMENT':
                parent_element = SubElement(element_tree, element.tag,
                    element.attrib)
                for child in element:
                    other_chid = SubElement(parent_element, child.tag,
                        child.attrib)
                    if not str(child.text).isspace() or\
                       child.text is not None:
                        other_chid.text = child.text

        linguisty_type_dict = dict()

        for linguisty in element_tree.findall('LINGUISTIC_TYPE'):
            key = linguisty.attrib['LINGUISTIC_TYPE_ID'].replace(' ','_')
            value = linguisty.attrib['TIME_ALIGNABLE']
            linguisty_type_dict[key] = value

        attrib_namespace = "{http://www.w3.org/XML/1998/namespace}"

        for tiers in root.findall('./header/tier_mapping/'):
            value = tiers.attrib['name'].replace(' ','_')
            for tiers_id in tiers:
                tier_id = tiers_id.text
                linguistic_type = value

                graf_tree = ET.parse(self.extinfofile.replace("-extinfo",
                    "-"+linguistic_type)).getroot()

                annotations = graf_tree.findall('{http://www.xces.org/ns/GrAF/1.0/}a')

                tier_element_tree = element_tree.find("TIER[@TIER_ID='"+tier_id+"']")

                linguistic_type_ref = tier_element_tree.attrib['LINGUISTIC_TYPE_REF'].replace(' ','_')

                for annotation in annotations:
                    features_map = {}

                    if tier_id+"/" in annotation.attrib['ref']:
                        if linguisty_type_dict[linguistic_type_ref] == 'true':
                            feature_structure = annotation[0]
                            annotation_value = feature_structure[0].text
                            time_slot_1 = feature_structure[2].text
                            time_slot_2 = feature_structure[1].text

                            features_map['ANNOTATION_ID'] = annotation.attrib[attrib_namespace+"id"]
                            features_map['TIME_SLOT_REF1'] = time_slot_1
                            features_map['TIME_SLOT_REF2'] = time_slot_2

                            annotation_element = SubElement(tier_element_tree,
                                'ANNOTATION')
                            alignable_annotation = SubElement(annotation_element,
                                'ALIGNABLE_ANNOTATION',features_map)
                            SubElement(alignable_annotation,
                                'ANNOTATION_VALUE').text = annotation_value
                        else:
                            feature_structure = annotation[0]
                            ref_annotation_id = feature_structure[0].text
                            annotation_value = feature_structure[2].text

                            features_map['ANNOTATION_ID'] = annotation.attrib[attrib_namespace+"id"]
                            features_map['ANNOTATION_REF'] = ref_annotation_id

                            for feature_element in feature_structure:
                                if feature_element.attrib['name'] != 'ref_annotation' and\
                                   feature_element.attrib['name'] != 'annotation_value' and\
                                   feature_element.attrib['name'] != 'tier_id':
                                    key = feature_element.attrib['name']
                                    features_map[key] = feature_element.text

                            annotation = SubElement(tier_element_tree, 'ANNOTATION')
                            ref_annotation = SubElement(annotation,
                                'REF_ANNOTATION',features_map)
                            SubElement(ref_annotation, 'ANNOTATION_VALUE').text =\
                            annotation_value

        file = open(self.outputfile,'wb')
        doc = minidom.parseString(tostring(element_tree))
        file.write(doc.toprettyxml(indent='    ', encoding='UTF-8'))
        file.close()
