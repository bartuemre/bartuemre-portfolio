"""Operator-declared source dependencies; copied feeds count as one lineage."""

from datetime import UTC, datetime


def resolve_roots(links):
    roots = {}
    for child in links:
        if child in roots:
            continue
        visited = set()
        path = []
        current = child
        while current in links and current not in roots:
            if current in visited:
                raise ValueError("Source lineage cannot contain a cycle")
            visited.add(current)
            path.append(current)
            current = links[current]
        root = roots.get(current, current)
        for node in path:
            roots[node] = root
    return roots


class LineageRegistry:
    def __init__(self, manager):
        self.manager = manager

    def list(self):
        with self.manager.connect() as connection:
            return [
                dict(row)
                for row in connection.execute("SELECT * FROM source_lineage ORDER BY child")
            ]

    def put(self, child, parent):
        if not all(isinstance(v, str) and 1 <= len(v.strip()) <= 128 for v in (child, parent)):
            raise ValueError("Lineage names must contain 1 to 128 characters")
        child, parent = child.strip(), parent.strip()
        with self.manager.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            links = dict(connection.execute("SELECT child,parent FROM source_lineage").fetchall())
            if child not in links and len(links) >= 1000:
                raise ValueError("Lineage mapping limit reached")
            links[child] = parent
            resolve_roots(links)
            connection.execute(
                "INSERT OR REPLACE INTO source_lineage VALUES (?, ?, ?)",
                (child, parent, datetime.now(UTC).isoformat()),
            )
        return {"child": child, "parent": parent, "root": resolve_roots(links)[child]}

    def remove(self, child):
        with self.manager.connect() as connection:
            connection.execute("DELETE FROM source_lineage WHERE child=?", (child,))
