import tests.u as u
import trelby.config as config

# tests for the paper size of new scripts


def testDefaultPaper():
    u.init()

    cfgGl = config.ConfigGlobal()
    assert cfgGl.defaultPaper == "A4"

    cfgGl.defaultPaper = "Letter"
    s = cfgGl.save()
    assert "DefaultPaper:Letter" in s

    cfgGl2 = config.ConfigGlobal()
    cfgGl2.load(s)
    assert cfgGl2.defaultPaper == "Letter"

    # unknown names fall back to A4
    cfgGl2.load("DefaultPaper:Tabloid\n")
    assert cfgGl2.defaultPaper == "A4"


def testSetPaper():
    u.init()

    cfg = config.Config()
    a4Lines = cfg.linesOnPage

    cfg.setPaper("Letter")
    assert (cfg.paperWidth, cfg.paperHeight) == (215.9, 279.4)

    # Letter is shorter, so fewer lines fit on a page
    assert cfg.linesOnPage < a4Lines

    cfg.setPaper("A4")
    assert (cfg.paperWidth, cfg.paperHeight) == (210.0, 297.0)
    assert cfg.linesOnPage == a4Lines
