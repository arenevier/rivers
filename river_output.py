#!/usr/bin/env python

# Copyright (C) 2010 Arnaud Renevier <arno@renevier.net>

import os, sys, shutil, psycopg2, glob, socket
from mako.template import Template

def createRiver(cursor, index, osm_id, name):
    print "computing river %s" % (name)
    river = River(osm_id, name)
    index[osm_id] = river
    sql = "SELECT r.osm_id, r.name FROM relations INNER JOIN tributaries ON relations.osm_id = tributaries.main_id INNER JOIN relations r ON tributaries.tributary_id = r.osm_id WHERE relations.osm_id = %s";
    cursor.execute(sql, (osm_id,))
    for (ch_osm_id, ch_name) in cursor.fetchall():
        if index.has_key(ch_osm_id):
            sys.stderr.write("trying to insert an already present river: #%s\n" % (ch_osm_id))
            continue
        tributary = createRiver(cursor, index, ch_osm_id, ch_name)
        river.childs.append(tributary)
    river.childs.sort(key=lambda r: r.length, reverse=True)

    sql = "WITH RECURSIVE t(geom) AS(SELECT (ST_Dump(geom)).geom AS geom FROM relations WHERE osm_id = %s UNION ALL SELECT ST_Union(f.geom, t.geom) FROM (SELECT (st_dump(geom)).geom AS geom FROM relations WHERE osm_id = %s) AS f, t  WHERE ST_StartPoint(f.geom) = ST_EndPoint(t.geom)) SELECT max(ST_Length(ST_LineMerge(geom), TRUE)) FROM t"
    cursor.execute(sql, (osm_id,osm_id))
    river.length = int(cursor.fetchone()[0] or 0)

    sql = "SELECT r1.osm_id, r1.name FROM relations r1 INNER JOIN relations r2 ON (ST_Intersects(r1.geom, r2.geom) AND r1.t = 'boundary') INNER JOIN (SELECT ST_DumpPoints(geom) AS geom FROM relations WHERE osm_id = %s) r3 ON ST_Intersects((r3.geom).geom, ST_MakePolygon(r1.geom)) WHERE r2.osm_id = %s ORDER BY (r3.geom).path"
    cursor.execute(sql, (osm_id,osm_id))
    seens = {}
    for (ci_osm_id, ci_name) in cursor.fetchall():
        if seens.has_key(ci_osm_id):
            continue
        river.cities.append((ci_osm_id, unicode(ci_name, 'utf-8')))
        seens[ci_osm_id] = True;

    sql = "SELECT w.osm_id, w.name FROM waysinrel INNER JOIN ways ON waysinrel.way_id = ways.osm_id INNER JOIN ways w ON ST_LineCrossingDirection(ways.geom, w.geom) != 0 WHERE w.t = 'bridge' AND waysinrel.rel_id = %s ORDER BY waysinrel.id, ST_Distance(w.geom, ST_StartPoint(ways.geom))"
    cursor.execute(sql, (osm_id,))
    for (br_osm_id, br_name) in cursor.fetchall():
        river.bridges.append((br_osm_id, unicode(br_name, 'utf-8')))

    return river

class River(object):
    def __init__(self, osm_id, name, childs=None, cities=None, bridges=None, length=0):
        self.osm_id = osm_id
        self.name = unicode(name, 'utf-8')
        self.length = length
        if childs:
            self.childs = childs
        else:
            self.childs = []
        if cities:
            self.cities = cities
        else:
            self.cities = []
        if bridges:
            self.bridges = bridges
        else:
            self.bridges = []

def outputriver(river):
    template = Template(filename='templates/river.html', input_encoding="utf-8", output_encoding="utf-8", strict_undefined=True)
    with open("htmloutput/%d.html" % (river.osm_id), "w") as fd:
        print "output for river #%d" % (river.osm_id)
        fd.write(template.render(river=river))
    for tributary in river.childs:
        outputriver(tributary)

if __name__ == '__main__':
    indextemplate = Template(filename='templates/index.html', input_encoding="utf-8", output_encoding="utf-8", strict_undefined=True)

    conn = psycopg2.connect("dbname=osm")
    cursor = conn.cursor()

    cursor.execute("SELECT osm_id, name FROM roots")

    index = {}
    roots = []
    for (osm_id, name) in cursor.fetchall():
        if index.has_key(osm_id):
            sys.stderr.write("trying to insert an already present river: #%s\n" % (osm_id))
            continue
        river = createRiver(cursor, index, osm_id, name)
        roots.append(river) 
    roots.sort(key=lambda r: r.length, reverse=True)

    shutil.rmtree("htmloutput", True);
    os.mkdir("htmloutput")
    for fname in (glob.glob("templates/*.js") + glob.glob("templates/*.png")):
        shutil.copy(fname, "htmloutput")

    with open("htmloutput/index.html", "w") as fd:
        print "generating main index"
        fd.write(indextemplate.render(roots=roots))

    cursor.execute("SELECT osm_id FROM relations WHERE t='river'")
    for river in roots:
        outputriver(river)

    conn.close()
