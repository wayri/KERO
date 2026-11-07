# LED current and manufacturer-part-number review

R6 and R7 change from 3.3 kohm to 4.7 kohm without changing their 0603 footprints or connectivity. For the same LED forward voltage this reduces ideal LED current by about 30%; brightness and battery life remain unmeasured.

The next commit assigns Vishay CRCW06034K70FKEA to both resistors. The manufacturer’s [D/CRCW e3 datasheet](https://www.vishay.com/docs/20035/dcrcwe3.pdf), part-number coding table and 0603 specifications support the 4.7 kohm, 1%, 0603 selection. This is a demonstration of MPN fields, not a stock or purchasing claim. The KiCad STEP model remains a generic 0603 envelope.

Compare commit 1 against main for the value changes, then commit 2 against commit 1 for Manufacturer/MPN/Rating/Datasheet metadata changes. Check both the schematic properties and PCB BoM.
