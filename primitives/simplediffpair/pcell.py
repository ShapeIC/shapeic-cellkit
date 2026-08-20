import gdsfactory as gf
from gdsfactory import Component
from ihp import PDK, tech
from ihp.cells import nmos
from shapeic_cellkit.utils import populate_via_stack

PDK.activate()
   
def get_sd_ports_even_odd(ref):
    sd_ports = []

    for p in ref.ports:
        if p.name.startswith("SD"):
            idx = int(p.name.replace("SD", ""))
            sd_ports.append((idx, p))

    sd_ports = sorted(sd_ports, key=lambda x: x[0])

    even_ports = [p for idx, p in sd_ports if idx % 2 == 0]
    odd_ports  = [p for idx, p in sd_ports if idx % 2 == 1]

    return even_ports, odd_ports

@gf.cell
def simplediffpair(
    length=0.4,
    width=5,
    nf=4,
    sep=0.5
) -> Component:

    c = Component("simplediffpair")

    nmos0 = c.add_ref(nmos(width=width, length=length, nf=nf))
    nmos1 = c.add_ref(nmos(width=width, length=length, nf=nf))
    nmos1.dxmin=nmos0.xmax+sep

    nmos0S, nmos0D = get_sd_ports_even_odd(nmos0)

    for port in nmos0S:
        populate_via_stack(
            c,
            column_width=port.width,
            row_width=0.3,
            center=port.center,
            bottom_layer="Metal1",
            top_layer="Metal2"
        )
    return c

if __name__ == "__main__":
    top = simplediffpair()
    top.write_gds("simplediffpair.gds")
