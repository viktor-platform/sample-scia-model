""""Copyright (c) 2022 VIKTOR B.V.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

VIKTOR B.V. PROVIDES THIS SOFTWARE ON AN "AS IS" BASIS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import itertools
from io import BytesIO
from pathlib import Path

import numpy as np

from viktor import Color
from viktor.core import ViktorController
from viktor.external.scia import Model as SciaModel
from viktor.external.scia import Material as SciaMaterial
from viktor.external.scia import LineSupport, LoadCase, LoadCombination, LoadGroup, OutputFileParser, PointSupport, \
    SciaAnalysis, SurfaceLoad
from viktor.geometry import CircularExtrusion, Extrusion, Line, Material, Point, Sphere
from viktor.result import DownloadResult
from viktor.views import GeometryResult, GeometryView, GeometryAndDataView, DataGroup, GeometryAndDataResult, \
    DataItem

from .parametrization import Parametrization


class FoundationController(ViktorController):
    label = 'Foundation'
    parametrization = Parametrization

    @GeometryView("3D", duration_guess=1)
    def visualize(self, params, **kwargs):
        scia_model = self.create_scia_model(params)
        geometries = self.create_visualization_geometries(params, scia_model)
        return GeometryResult(geometries)

    @GeometryAndDataView("SCIA result", duration_guess=60)
    def run_scia(self, params, **kwargs):
        scia_model = self.create_scia_model(params)

        # create input files
        input_xml, input_def = scia_model.generate_xml_input()
        input_esa = self.get_scia_input_esa()

        # analyze SCIA model
        scia_analysis = SciaAnalysis(input_xml, input_def, input_esa)
        scia_analysis.execute(300)  # timeout after 5 minutes
        scia_result = scia_analysis.get_xml_output_file()

        # parse analysis result
        result = OutputFileParser.get_result(scia_result, "Reactions", parent='Combinations - C1')
        reactions = result['Nodal reactions']

        max_rz = float(max(reactions['R_z']))
        data_result = DataGroup(
            DataItem('SCIA results', ' ', subgroup=DataGroup(
                DataItem('Maximum pile reaction', max_rz, suffix='N', number_of_decimals=2)
            ))
        )

        geometries = self.create_visualization_geometries(params, scia_model)
        return GeometryAndDataResult(geometries, data_result)

    def download_scia_input_esa(self, params, **kwargs):
        scia_input_esa = self.get_scia_input_esa()

        filename = "model.esa"
        return DownloadResult(scia_input_esa, filename)

    def download_scia_input_xml(self, params, **kwargs):
        scia_model = self.create_scia_model(params)
        input_xml, _ = scia_model.generate_xml_input()

        return DownloadResult(input_xml, 'test.xml')

    def download_scia_input_def(self, params, **kwargs):
        m = SciaModel()
        _, input_def = m.generate_xml_input()
        return DownloadResult(input_def, 'viktor.xml.def')

    def get_scia_input_esa(self) -> BytesIO:
        esa_path = Path(__file__).parent / 'scia' / 'model.esa'
        scia_input_esa = BytesIO()
        with open(esa_path, "rb") as esa_file:
            scia_input_esa.write(esa_file.read())
        return scia_input_esa

    def create_scia_model(self, params) -> SciaModel:
        model = SciaModel()

        '''
        STRUCTURE
        '''
        # create nodes at the slab corners
        width_x = params.geometry.slab.width_x * 1e-03
        width_y = params.geometry.slab.width_y * 1e-03
        n1 = model.create_node('n1', 0, 0, 0)  # origin
        n2 = model.create_node('n2', 0, width_y, 0)
        n3 = model.create_node('n3', width_x, width_y, 0)
        n4 = model.create_node('n4', width_x, 0, 0)

        # create the pile nodes
        number_of_piles_x = 4
        number_of_piles_y = 3
        pile_edge_distance = 0.3
        pile_length = params.geometry.piles.length

        start_x = pile_edge_distance
        end_x = width_x - pile_edge_distance
        x = np.linspace(start_x, end_x, number_of_piles_x)
        start_y = pile_edge_distance
        end_y = width_y - pile_edge_distance
        y = np.linspace(start_y, end_y, number_of_piles_y)
        pile_positions = np.array(list(itertools.product(x, y)))

        pile_top_nodes = []
        pile_bottom_nodes = []
        for pile_id, (pile_x, pile_y) in enumerate(pile_positions, 1):
            n_top = model.create_node(f'K:p{pile_id}_t', pile_x, pile_y, 0)
            n_bottom = model.create_node(f'K:p{pile_id}_b', pile_x, pile_y, -pile_length)
            pile_top_nodes.append(n_top)
            pile_bottom_nodes.append(n_bottom)

        # create pile beams
        pile_diameter = params.geometry.piles.diameter * 1e-03
        material = SciaMaterial(0, 'C30/37')
        cross_section = model.create_circular_cross_section('concrete_pile', material, pile_diameter)
        pile_beams = []
        for pile_id, (n_top, n_bottom) in enumerate(zip(pile_top_nodes, pile_bottom_nodes), 1):
            pile_beam = model.create_beam(n_top, n_bottom, cross_section)
            pile_beams.append(pile_beam)

        # create the concrete slab
        material = SciaMaterial(0, 'concrete_slab')
        thickness = params.geometry.slab.thickness * 1e-03
        corner_nodes = [n1, n2, n3, n4]
        slab = model.create_plane(corner_nodes, thickness, name='foundation slab', material=material)

        '''
        SUPPORTS
        '''

        # create pile point supports
        freedom_v = (
            PointSupport.Freedom.FREE, PointSupport.Freedom.FREE, PointSupport.Freedom.FLEXIBLE,
            PointSupport.Freedom.FREE, PointSupport.Freedom.FREE, PointSupport.Freedom.FREE
        )
        kv = 400 * 1e06
        stiffness_v = (0, 0, kv, 0, 0, 0)
        for pile_id, pile_beam in enumerate(pile_beams, 1):
            n_bottom = pile_beam.end_node
            model.create_point_support(f'Sn:p{pile_id}', n_bottom, PointSupport.Type.STANDARD,
                                       freedom_v, stiffness_v, PointSupport.CSys.GLOBAL)

        # create pile line supports
        kh = 10 * 1e06
        for pile_id, pile_beam in enumerate(pile_beams, 1):
            model.create_line_support_on_beam(pile_beam, x=LineSupport.Freedom.FLEXIBLE, stiffness_x=kh,
                                              y=LineSupport.Freedom.FLEXIBLE, stiffness_y=kh,
                                              z=LineSupport.Freedom.FREE, rx=LineSupport.Freedom.FREE,
                                              ry=LineSupport.Freedom.FREE, rz=LineSupport.Freedom.FREE,
                                              c_sys=LineSupport.CSys.GLOBAL)

        # create the slab supports
        stiffness_x = 50 * 1e06
        stiffness_y = 50 * 1e06
        for edge in (1, 3):
            model.create_line_support_on_plane((slab, edge),
                                               x=LineSupport.Freedom.FLEXIBLE, stiffness_x=stiffness_x,
                                               y=LineSupport.Freedom.FREE,
                                               z=LineSupport.Freedom.FREE,
                                               rx=LineSupport.Freedom.FREE,
                                               ry=LineSupport.Freedom.FREE,
                                               rz=LineSupport.Freedom.FREE)
        for edge in (2, 4):
            model.create_line_support_on_plane((slab, edge),
                                               x=LineSupport.Freedom.FREE,
                                               y=LineSupport.Freedom.FLEXIBLE, stiffness_y=stiffness_y,
                                               z=LineSupport.Freedom.FREE,
                                               rx=LineSupport.Freedom.FREE,
                                               ry=LineSupport.Freedom.FREE,
                                               rz=LineSupport.Freedom.FREE)

        '''
        SETS
        '''
        # create the load group
        lg = model.create_load_group('LG1', LoadGroup.LoadOption.VARIABLE, LoadGroup.RelationOption.STANDARD,
                                     LoadGroup.LoadTypeOption.CAT_G)

        # create the load case
        lc = model.create_variable_load_case('LC1', 'first load case', lg, LoadCase.VariableLoadType.STATIC,
                                             LoadCase.Specification.STANDARD, LoadCase.Duration.SHORT)

        # create the load combination
        load_cases = {
            lc: 1
        }

        model.create_load_combination('C1', LoadCombination.Type.ENVELOPE_SERVICEABILITY, load_cases)

        '''
        LOADS
        '''
        # create the load
        force = params.loads.input.uniform_load * 1e03
        force *= -1  # in negative Z-direction
        model.create_surface_load('SF:1', lc, slab, SurfaceLoad.Direction.Z, SurfaceLoad.Type.FORCE, force,
                                  SurfaceLoad.CSys.GLOBAL, SurfaceLoad.Location.LENGTH)

        return model

    def create_visualization_geometries(self, params, scia_model):
        geometries = []
        for node in scia_model.nodes:
            node_obj = Sphere(Point(node.x, node.y, node.z), params.geometry.slab.width_y * 1e-05)
            node_obj.material = Material('node', color=Color(0, 255, 0))
            geometries.append(node_obj)

        # pile beams
        pile_diameter = params.geometry.piles.diameter * 1e-03
        for beam in scia_model.beams:
            point_top = Point(beam.begin_node.x, beam.begin_node.y, beam.begin_node.z)
            point_bottom = Point(beam.end_node.x, beam.end_node.y, beam.end_node.z)
            beam_obj = CircularExtrusion(pile_diameter, Line(point_top, point_bottom))
            beam_obj.material = Material('beam', threejs_roughness=1, threejs_opacity=0.3)
            geometries.append(beam_obj)

        corner_points = [
            Point(scia_model.nodes[0].x, scia_model.nodes[0].y, scia_model.nodes[0].z),
            Point(scia_model.nodes[1].x, scia_model.nodes[1].y, scia_model.nodes[1].z),
            Point(scia_model.nodes[2].x, scia_model.nodes[2].y, scia_model.nodes[2].z),
            Point(scia_model.nodes[3].x, scia_model.nodes[3].y, scia_model.nodes[3].z),
            Point(scia_model.nodes[0].x, scia_model.nodes[0].y, scia_model.nodes[0].z)
        ]

        thickness = params.geometry.slab.thickness * 1e-03
        slab_obj = Extrusion(corner_points, Line(Point(0, 0, -thickness / 2), Point(0, 0, thickness / 2)))
        slab_obj.material = Material('slab', threejs_roughness=1, threejs_opacity=0.3)
        geometries.append(slab_obj)

        return geometries
