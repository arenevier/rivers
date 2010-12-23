--- relations table
DROP TYPE IF EXISTS reltype CASCADE;
CREATE TYPE reltype AS ENUM ('river', 'boundary');

DROP TABLE IF EXISTS relations CASCADE;
CREATE TABLE relations (osm_id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, t reltype);
SELECT AddGeometryColumn('relations', 'geom', 4326, 'GEOMETRY', 2);

--- tributaries table
DROP TABLE IF EXISTS tributaries;
CREATE TABLE tributaries (id SERIAL PRIMARY KEY, main_id INTEGER NOT NULL, tributary_id INTEGER NOT NULL);

--- waysinrel table
DROP TABLE IF EXISTS waysinrel;
CREATE TABLE waysinrel (id SERIAL PRIMARY KEY, rel_id INTEGER NOT NULL, way_id INTEGER NOT NULL);

CREATE INDEX waysinrel_relid_seq on waysinrel (rel_id);
CREATE INDEX waysinrel_wayid_seq on waysinrel (way_id);

--- ways table
DROP TYPE IF EXISTS waytype CASCADE;
CREATE TYPE waytype AS ENUM ('bridge');

DROP TABLE IF EXISTS ways CASCADE;
CREATE TABLE ways (osm_id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, t waytype DEFAULT NULL);
SELECT AddGeometryColumn('ways', 'geom', 4326, 'LINESTRING', 2);

CREATE OR REPLACE FUNCTION waysdrop() RETURNS TRIGGER AS $$ BEGIN IF NEW.t IS NOT NULL OR EXISTS (SELECT * FROM waysinrel WHERE way_id = NEW.osm_id) THEN RETURN NEW; ELSE RETURN NULL; END IF; END; $$ LANGUAGE PLPGSQL;
DROP TRIGGER IF EXISTS waysdrop ON ways;
CREATE TRIGGER waysdrop BEFORE INSERT ON ways FOR EACH ROW EXECUTE PROCEDURE waysdrop();

--- nodesinway table
DROP TABLE IF EXISTS nodesinway;
CREATE TABLE nodesinway (id SERIAL PRIMARY KEY, way_id INTEGER NOT NULL, node_id INTEGER NOT NULL);

CREATE INDEX nodesinway_wayid_seq on nodesinway (way_id);
CREATE INDEX nodesinway_nodeid_seq on nodesinway (node_id);

CREATE OR REPLACE FUNCTION nodesinwaydrop() RETURNS TRIGGER AS $$ BEGIN IF EXISTS (SELECT * FROM ways WHERE osm_id = NEW.way_id) THEN RETURN NEW; ELSE RETURN NULL; END IF; END; $$ LANGUAGE PLPGSQL;
DROP TRIGGER IF EXISTS nodesinwaydrop ON nodesinway;
CREATE TRIGGER nodesinwaydrop BEFORE INSERT ON nodesinway FOR EACH ROW EXECUTE PROCEDURE nodesinwaydrop();

--- nodes table
DROP TABLE IF EXISTS nodes;
CREATE TABLE nodes (osm_id INTEGER PRIMARY KEY);
SELECT AddGeometryColumn('nodes', 'geom', 4326, 'POINT', 2);

CREATE OR REPLACE FUNCTION nodesdrop() RETURNS TRIGGER AS $$ BEGIN IF EXISTS (SELECT * FROM nodesinway WHERE node_id = NEW.osm_id) THEN RETURN NEW; ELSE RETURN NULL; END IF; END; $$ LANGUAGE PLPGSQL;
DROP TRIGGER IF EXISTS nodesdrop ON nodes;
CREATE TRIGGER nodesdrop BEFORE INSERT ON nodes FOR EACH ROW EXECUTE PROCEDURE nodesdrop();

--
-- roots view
-- 

CREATE OR REPLACE VIEW roots AS (SELECT relations.* FROM relations LEFT OUTER JOIN tributaries ON tributary_id = osm_id WHERE tributary_id IS NULL and t = 'river');

--
-- helper functions
-- 

CREATE OR REPLACE FUNCTION waygeom(integer) RETURNS geometry AS $$ DECLARE points geometry; BEGIN SELECT INTO points ST_Collect(geom) FROM (SELECT nodes.geom AS geom FROM ways INNER JOIN nodesinway ON ways.osm_id = nodesinway.way_id INNER JOIN nodes ON nodesinway.node_id = nodes.osm_id WHERE ways.osm_id = $1 ORDER BY nodesinway.id) AS f; IF ST_NPoints(points) >= 2 THEN RETURN ST_GeomFromEWKT(replace(st_asewkt(points), 'MULTIPOINT', 'LINESTRING')); ELSE RETURN NULL; END IF; END; $$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION boundarygeom(integer) RETURNS geometry AS $$ DECLARE polygons geometry; ring geometry; BEGIN SELECT INTO polygons ST_Polygonize(geom) FROM (SELECT ways.geom AS geom FROM relations INNER JOIN waysinrel ON relations.osm_id = waysinrel.rel_id INNER JOIN ways on waysinrel.way_id = ways.osm_id WHERE relations.osm_id = $1 AND ways.geom IS NOT NULL ORDER BY waysinrel.id) AS f; IF ST_NumGeometries(polygons) = 1 THEN SELECT ST_ExteriorRing(GeometryN(polygons,1)) INTO ring; IF ST_IsClosed(ring) THEN RETURN ring; END IF; END IF; RETURN NULL; END; $$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION rivergeom(integer) RETURNS geometry AS $$ BEGIN RETURN ST_Collect(geom) FROM (SELECT ways.geom as geom FROM relations INNER JOIN waysinrel ON relations.osm_id = waysinrel.rel_id OR relations.osm_id = waysinrel.rel_id INNER JOIN ways ON waysinrel.way_id = ways.osm_id WHERE relations.osm_id = $1 ORDER BY waysinrel.id) AS f; END; $$ LANGUAGE plpgsql STABLE;
