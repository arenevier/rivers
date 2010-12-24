#!/usr/bin/env python

# Copyright (C) 2010 Arnaud Renevier <arno@renevier.net>

import xml.sax.handler
import sys, psycopg2, UserDict, os

class Point(object):
    def __init__(self, lon, lat):
        self.lon = float(lon)
        self.lat = float(lat)
        if self.lon < -180 or self.lon > 180:
            raise ValueError
        if self.lat < -90 or self.lat > 90:
            raise ValueError

psycopg2.extensions.register_adapter(Point, lambda p: psycopg2.extensions.AsIs("ST_GeometryFromText('POINT(%f %f)', 4326)" % (p.lon, p.lat)))

class Node(UserDict.UserDict):
    def __init__(self, osm_id, lon, lat):
        self.data = { 'osm_id': int(osm_id),
                      'geom': Point(lon, lat)
                    }

    def __int__(self):
        return self['osm_id']

    def __str__(self):
        return ("Node #%d: <%f, %f>" % (self['osm_id'], self['geom'].lon, self['geom'].lat))

class Way(UserDict.UserDict):
    def __init__(self, osm_id, name=None, nodes=None, bridge=None, ref=None):
        self.data = { 'osm_id': int(osm_id)
                    }
        if nodes:
            self.nodes = nodes
        else:
            self.nodes = []

        self._name = name
        self.bridge = bridge
        self.ref = ref

    def __getitem__(self, key):
        if key == "type":
            if self.bridge == "yes":
                return "bridge"
            else:
                return None
        elif key == "name":
            if self._name:
                return self._name
            if self.ref:
                return self.ref
            else:
                return "#" + str(self['osm_id'])
        return UserDict.UserDict.__getitem__(self, key)

    def __setitem__(self, key, value):
        if key == "name":
            self._name = value
        else:
            UserDict.UserDict.__setitem__(self, key, value)

    def __int__(self):
        return self['osm_id']

    def __str__(self):
        return "Way #%d, %s" % (self['osm_id'], self['name'])

class Relation(UserDict.UserDict):
    def __init__(self, osm_id, name=None, 
                ways=None, tributaries=None, waterway=None, reltype=None, 
                admin_level=None, boundary=None, sandre=""):
        self.data = { 'osm_id': int(osm_id)
                    }

        self._name = name
        self.waterway = waterway
        self.type = reltype

        self.admin_level = admin_level
        self.boundary = boundary

        self.sandre = sandre

        if ways:
            self.ways = ways
        else:
            self.ways = []
        if tributaries:
            self.tributaries = tributaries
        else:
            self.tributaries = []

    def __getitem__(self, key):
        if key == "type":
            if self.type == "waterway" and self.waterway in ["river", "stream"]:
                return "river"
            elif self.admin_level == "8" and self.boundary == "administrative":
                return "boundary"
            else:
                return None
        elif key == "name":
            if self._name:
                return self._name
            else:
                return "#" + str(self['osm_id'])
        return UserDict.UserDict.__getitem__(self, key)

    def __setitem__(self, key, value):
        if key == "name":
            self._name = value
        else:
            UserDict.UserDict.__setitem__(self, key, value)

    def __int__(self):
        return self['osm_id']

    def __str__(self):
        res = "Relation #%d" % (self['osm_id'])
        if self['name']:
            res += ", %s" % (self['name'].encode("utf-8"))
        return res

class OsmHandler(xml.sax.handler.ContentHandler): 
    usecopy = True
    tables = [('relations', ['osm_id', 'name', 't', 'sandre'], None),
              ('tributaries', ['main_id', 'tributary_id'], None),
              ('waysinrel', ['rel_id', 'way_id'], 'waysinrel_relid_seq'),
              ('ways', ['osm_id', 'name', 't'], None),
              ('nodesinway', ['way_id', 'node_id'], 'nodesinway_wayid_seq'),
              ('nodes', ['osm_id', 'geom'], None),
    ]

    def __init__(self, cursor):
        self.cursor = cursor
        self.resetstate()

        if self.usecopy:
            self.files = {}
            if not os.path.exists("tmp"):
                os.mkdir("tmp")
            elif not os.path.isdir("tmp"):
                raise StandardError, "tmp exists and is not a directory"
            for (table, _, _) in self.tables:
                self.files[table] = open("tmp/" + table + "_data", "w")
        else:
            self.cursor.execute("PREPARE insnodes (INT, GEOMETRY) AS INSERT INTO nodes (osm_id, geom) VALUES($1, $2)")
            self.cursor.execute("PREPARE insways (INT, VARCHAR) AS INSERT INTO ways (osm_id, name) VALUES ($1, $2)")
            self.cursor.execute("PREPARE insnodesinway (INT, INT) AS INSERT INTO nodesinway (way_id, node_id) VALUES ($1, $2)")
            self.cursor.execute("PREPARE insrelations (INT, VARCHAR, reltype) AS INSERT INTO relations (osm_id, name, t) VALUES ($1, $2, $3)")
            self.cursor.execute("PREPARE inswaysinrel (INT, INT) AS INSERT INTO waysinrel (rel_id, way_id) VALUES ($1, $2)")
            self.cursor.execute("PREPARE instributaries (INT, INT) AS INSERT INTO tributaries (main_id, tributary_id) VALUES ($1, $2)")


    def endDocument(self):
        if self.usecopy: 
            for (table, columns, index) in self.tables:
                print "copying table %s" % (table)
                self.files[table].close()
                fd = open("tmp/" + table + "_data", "r")
                self.cursor.copy_from(fd, table, sep="|", columns=columns, null='')
                fd.close()
#                if (index):
 #                   self.cursor.execute("CLUSTER %s USING %s" % (table, index))
                cursor.execute("VACUUM ANALYZE %s" % (table))

    def resetstate(self):
        self._currel = None
        self._curway = None
        self._curnode = None

    def startElement(self, name, attrs):
        if name == "node":
            try:
                self._curnode = Node(attrs.get('id'), attrs.get('lon'), attrs.get('lat'))
            except:
                return

        elif name == "way":
            try:
                self._curway = Way(attrs.get('id'))
            except:
                return

        elif name == "relation":
            try:
                self._currel = Relation(attrs.get('id'))
            except:
                return

        elif name == "nd":
            try:
                ref = int(attrs.get('ref'))
            except Exception:
                return
            if self._curway is not None:
                self._curway.nodes.append(ref)

        elif name == "member":
            try:
                ref = int(attrs.get('ref'))
            except Exception:
                return
            if self._currel is not None:
                if attrs.get('type') == 'way':
                    self._currel.ways.append(ref)
                elif attrs.get('type') == 'relation' and attrs.get('role') == 'tributary':
                    self._currel.tributaries.append(ref)

        elif name == "tag":
            key = attrs.get('k')
            value = attrs.get('v')
            if key == "name":
                if self._curway:
                    self._curway['name'] = value
                elif self._currel:
                    self._currel['name'] = value
            elif self._currel:
                if key in ['type', 'waterway', 'admin_level', 'boundary']:
                    setattr(self._currel, key, value)
                elif key == 'ref:sandre':
                    self._currel.sandre = value
            elif self._curway:
                if key in ['bridge', 'ref']:
                    setattr(self._curway, key, value)

    def endElement(self, name):
        if name == "node":
            if self._curnode:
                print (("adding %s") % (self._curnode))
                if self.usecopy:
                    self.files['nodes'].write("%d|SRID=4326;POINT(%f %f)\n" % (self._curnode['osm_id'], self._curnode['geom'].lon, self._curnode['geom'].lat))
                else:
                    self.cursor.execute("EXECUTE insnodes (%(osm_id)s, %(geom)s)", (self._curnode))
            self.resetstate()

        elif name == "way":
            if self._curway:
                waytype = self._curway['type'] or ''
                print (("adding %s") % (self._curway))

                if self.usecopy:
                    self.files['ways'].write("%d|%s|%s\n" % (self._curway['osm_id'], self._curway['name'].encode("utf-8").replace('|', '\|'), waytype))
                    for ref in self._curway.nodes:
                        self.files['nodesinway'].write("%d|%d\n" % (int(self._curway), int(ref)))
                else:
                    self.cursor.execute("EXECUTE insways (%(osm_id)s, %(name)s)", (self._curway))
                    relations = [(int(self._curway), int(ref)) for ref in self._curway.nodes]
                    self.cursor.executemany("EXECUTE insnodesinway (%s, %s)", relations)
            self.resetstate()

        elif name == "relation":
            if self._currel:
                reltype = self._currel['type']

                if reltype in ['river', 'boundary']:
                    print (("adding %s") % (self._currel))

                    if self.usecopy:
                        if self._currel['name']:
                            self.files['relations'].write("%d|%s|%s|%s\n" % (self._currel['osm_id'], self._currel['name'].encode("utf-8").replace('|', '\|'), reltype, self._currel.sandre))
                        else:
                            self.files['relations'].write("%d||%s|%s\n" % (self._currel['osm_id'], reltype, self._currel.sandre))

                        for ref in self._currel.ways:
                            self.files['waysinrel'].write("%d|%d\n" % (int(self._currel), int(ref)))
                        for trib in self._currel.tributaries:
                            self.files['tributaries'].write("%d|%d\n" % (int(self._currel), int(trib)))
                    else:
                        self.cursor.execute("EXECUTE insrelations (%(osm_id)s, %(name)s, %(type)s)", (self._currel))
                        relations = [(int(self._currel), int(ref)) for ref in self._currel.ways]
                        self.cursor.executemany("EXECUTE inswaysinrel (%s, %s)", relations)
                        relations = [(int(self._currel), int(trib)) for trib in self._currel.tributaries]
                        self.cursor.executemany("EXECUTE instributaries (%s, %s)", relations)

            self.resetstate()


def createschema(cursor):
    with open ("schema.sql") as schema:
        for line in schema.readlines():
            command = line[:-1]
            if command:
                # discard sql comments
                if len(line) < 2 or (line[0] is not '-' and line[1] is not '-'):
                    cursor.execute(line[:-1])

if __name__ == '__main__':
    conn = psycopg2.connect("dbname=osm")
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    createschema(cursor)

    parser = xml.sax.make_parser()
    parser.setContentHandler(OsmHandler(cursor))
    try:
        if sys.argv[1].endswith('.bz2'):
            import bz2
            f = bz2.BZ2File(sys.argv[1])
        else:
            f = sys.argv[1]
        parser.parse(f)
        print "computing way geometries"
        cursor.execute("update ways set geom = waygeom(osm_id)")
        print "computing relation geometries"
        cursor.execute("update relations set geom = boundarygeom(osm_id) where t = 'boundary'")
        cursor.execute("update relations set geom = rivergeom(osm_id) where t = 'river'")
    except Exception, e:
        import traceback
        traceback.print_exc()
    cursor.close()
    conn.close()
