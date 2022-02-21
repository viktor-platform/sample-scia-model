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
from viktor.parametrization import Parametrization as ParametrizationBaseClass
from viktor.parametrization import Tab, Section, NumberField, DownloadButton


class Parametrization(ParametrizationBaseClass):
    geometry = Tab("Geometry")
    geometry.slab = Section("Slab")
    geometry.slab.width_x = NumberField("Width in x", suffix="mm", default=6000)
    geometry.slab.width_y = NumberField("Width in y", suffix="mm", default=5000)
    geometry.slab.thickness = NumberField("Thickness", suffix="mm", default=500)

    geometry.piles = Section("Piles")
    geometry.piles.diameter = NumberField("Diameter", suffix="mm", default=500)
    geometry.piles.length = NumberField("Length", suffix="m", default=7)

    loads = Tab("Loads")
    loads.input = Section("Input")
    loads.input.uniform_load = NumberField("Uniform load", suffix="kN/m2", default=1)

    scia = Tab("SCIA")
    scia.downloads = Section("Downloads")
    scia.downloads.input_xml_btn = DownloadButton("Input .xml", method="download_scia_input_xml")
    scia.downloads.input_def_btn = DownloadButton("Input .def", method="download_scia_input_def")
    scia.downloads.input_esa_btn = DownloadButton("Input .esa", method="download_scia_input_esa")
