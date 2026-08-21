import gdsfactory as gf
from gdsfactory import Component
from ihp import PDK
from ihp.cells import pmos
from ihp.cells.passives import guard_ring
from shapeic_cellkit.utils import connect_ports_to_bus, connect_gates_to_bus, get_sd_ports_even_odd

PDK.activate()



@gf.cell
def simplecurrentmirror(
    length=0.4,
    width=5,
    nf=4,
    sep=0.5
) -> Component:

    wf=width/nf
    polyExt=0.18
    routingSpacing=0.4

    c = Component("simplecurrentmirror")

    pmos0 = c.add_ref(pmos(width=width, length=length, nf=nf))
    pmos1 = c.add_ref(pmos(width=width, length=length, nf=nf))
    pmos1.dxmin=pmos0.xmax+sep

    pmos0S, pmos0D = get_sd_ports_even_odd(pmos0)
    pmos1S, pmos1D = get_sd_ports_even_odd(pmos1)

    connect_ports_to_bus(
        c,
        pmos0S+pmos1S,
        distance=wf/2+polyExt+routingSpacing,
        layer="Metal2drawing",
        bus_side="top",
        pin_name="S"
    )
    connect_ports_to_bus(
        c,
        pmos0D,
        distance=wf/2-0.32/2,
        layer="Metal2drawing",
        bus_side="bottom",
        pin_name="D0"
    )
    connect_ports_to_bus(
        c,
        pmos1D,
        distance=wf/2-0.32/2,
        layer="Metal2drawing",
        bus_side="bottom",
        pin_name="D1"
    )
    connect_gates_to_bus(
        c,
        pmos0,
        length,
        "GatPolydrawing",
        pin_name="G0"
    )
    connect_gates_to_bus(
        c,
        pmos1,
        length,
        "GatPolydrawing",
        pin_name="G1"
    )

    polyBusWidth=0.3

    c.add_polygon(
        [
            (c.ports["G0"].center[0], c.ports["G0"].center[1]-polyBusWidth/2),
            (c.ports["G1"].center[0], c.ports["G0"].center[1]-polyBusWidth/2),
            (c.ports["G1"].center[0], c.ports["G0"].center[1]+polyBusWidth/2),
            (c.ports["G0"].center[0], c.ports["G0"].center[1]+polyBusWidth/2),
        ],
        layer="Metal1drawing"
    )

    guard_bbox = (
        (c.xmin, c.ymin),
        (c.xmax, c.ymax)
    )
    c.add_polygon(
        [
            (c.xmin-0.32, c.ymin-0.32),
            (c.xmax+0.32, c.ymin-0.32),
            (c.xmax+0.32, c.ymax+0.32),
            (c.xmin-0.32, c.ymax+0.32),
        ],
        layer="NWelldrawing"
    )
    c.add_ref(
        guard_ring(
            width=0.32,
            guardRingSpacing=0.3,
            guardRingType="nwell",
            bbox=guard_bbox
        )
    )

    return c

if __name__ == "__main__":
    top = simplecurrentmirror()
    top.write_gds("simplecurrentmirror.gds")
