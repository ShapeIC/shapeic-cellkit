import gdsfactory as gf
from gdsfactory import Component
from gdsfactory.components import bbox
from ihp import PDK, tech
from ihp.cells import nmos
from ihp.cells.passives import guard_ring
from shapeic_cellkit.utils import populate_via_stack, connect_ports_to_bus, connect_gates_to_bus

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

    wf=width/nf
    polyExt=0.18
    routingSpacing=0.4

    c = Component("simplediffpair")

    nmos0 = c.add_ref(nmos(width=width, length=length, nf=nf))
    nmos1 = c.add_ref(nmos(width=width, length=length, nf=nf))
    nmos1.dxmin=nmos0.xmax+sep

    nmos0S, nmos0D = get_sd_ports_even_odd(nmos0)
    nmos1S, nmos1D = get_sd_ports_even_odd(nmos1)

    connect_ports_to_bus(
        c,
        nmos0S+nmos1S,
        distance=wf/2-0.32/2,
        layer="Metal2drawing",
        bus_side="bottom",
        pin_name="S"
    )
    connect_ports_to_bus(
        c,
        nmos0D,
        distance=wf/2+polyExt+routingSpacing,
        layer="Metal2drawing",
        bus_side="top",
        pin_name="D0"
    )
    connect_ports_to_bus(
        c,
        nmos1D,
        distance=wf/2+polyExt+routingSpacing,
        layer="Metal2drawing",
        bus_side="top",
        pin_name="D1"
    )

    connect_gates_to_bus(
        c,
        nmos0,
        length,
        "GatPolydrawing",
        pin_name="G0"
    )
    connect_gates_to_bus(
        c,
        nmos1,
        length,
        "GatPolydrawing",
        pin_name="G1"
    )

    guard_bbox = (
        (c.xmin, c.ymin),
        (c.xmax, c.ymax)
    )
    c.add_ref(
        guard_ring(
            width=0.32,
            guardRingSpacing=0.3,
            guardRingType="psub",
            bbox=guard_bbox
        )
    )
   
    return c


if __name__ == "__main__":
    top = simplediffpair()
    top.write_gds("simplediffpair.gds")
