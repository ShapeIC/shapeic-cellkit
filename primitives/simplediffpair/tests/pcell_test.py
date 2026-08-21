from gdsfactory import Component

from ..pcell import simplediffpair
import numpy as np

if __name__ == "__main__":

    c = Component("top")

    widths = [5, 10, 20, 30]
    lengths = [0.4, 0.8, 1.6, 6.4]
    nf = [1, 2, 3, 5]

    prev_xmax = 0

    for width, length, nf in zip(widths, lengths, nf):
        df = c.add_ref(simplediffpair(
            length=length,
            width=width,
            nf=nf
        ))
        df.xmin = prev_xmax+1

        prev_xmax = c.xmax

    c.write_gds("simplediffpair_test.gds")
