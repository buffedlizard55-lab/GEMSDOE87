# Active lane: H87-FRB only

**H87-FRB — Fabric-rotation boundary under active strain.** The sole active method
uses a label-free, multiscale double-angle rotation/discordance signal from
detrended elevation (band 12), total magnetic intensity (band 14), and isostatic
gravity anomaly (band 13), corroborated by gradients in geodetic shear/dilation
(bands 7–8) and conductivity (band 17). It targets buried or oblique transfer
structures that rotate physical fabric without a single conspicuous mapped scarp.
The named non-fault mimics are lithologic or volcanic contacts, drainage divides,
and processing seams. Registry rasters are used only after model fitting for
surface/final-dot duplicate gates; they are not training or placement inputs.

The current release passed the written duplicate thresholds against 360 selected
public candidate rasters: maximum exact surface Spearman 0.33455022458271244,
maximum final binary Spearman 0.022245447786212274, and maximum final 3-pixel overlap
0.6641324781599027 (strict stop condition `> 0.70`). A new method must use a new
lane declaration and re-run both checks before placement.
