import gdsfactory as gf
from gdsfactory import Component
from ihp import PDK, tech
from ihp.cells import via_stack
from ihp.cells import place_contacts

def populate_via_stack(c, column_width=10.0, row_width=10.0, center=[0,0], bottom_layer="Metal1", top_layer="Metal2"):

        
    via1_size = tech.TECH.via1_size_rf
    via1_spacing = tech.TECH.via1_spacing_wide
    via1_enc = tech.TECH.via1_enc

    column_num_float = (column_width-via1_enc+via1_spacing)/(via1_size+via1_spacing)
    column_num_int = int(column_num_float)
    column_num_dec = column_num_float-column_num_int

    row_num_float = (row_width-via1_enc+via1_spacing)/(via1_size+via1_spacing)
    row_num_int = int(row_num_float)

    via_stack1 = c.add_ref(via_stack(bottom_layer=bottom_layer, top_layer=top_layer, vn_columns=row_num_int, vn_rows=column_num_int, size=(row_width, column_width)))
    via_stack1.x=center[0]
    via_stack1.y=center[1]

    return via_stack1

def populate_contact(c, column_width=10.0, row_width=10.0, center=[0, 0]):

    cont_size = tech.TECH.cont_size
    cont_spacing = tech.TECH.cont_spacing

    xl = center[0]-row_width/2
    yl = center[1]-column_width/2
    xh = center[0]+row_width/2
    yh = center[1]+column_width/2
    ox = 0
    oy = tech.TECH.cont_enc_active

    place_contacts(
        c,
        "Contdrawing",
        xl=xl,
        yl=yl,
        xh=xh,
        yh=yh,
        ox=ox,
        oy=oy,
        ws=cont_size,
        ds=cont_spacing
    )

    c.add_polygon(
        [
            (xl, yl),
            (xh, yl),
            (xh, yh),
            (xl, yh)
        ],
        layer="Metal1drawing"
    )
    
