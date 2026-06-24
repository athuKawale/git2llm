import hashlib
from datasketch import MinHash, MinHashLSH
from git2llm.models import CommitRecord

class Deduplicator:
    def __init__(self, threshold: float = 0.85, method: str = "minhash"):
        self.method = method
        self.threshold = threshold
        self.exact_hashes = set()
        if method == "minhash":
            self.lsh = MinHashLSH(threshold=threshold, num_perm=128)
        else:
            self.lsh = None

    def add_and_check(self, record_id: str, message: str, diff: str) -> bool:
        """
        Check if the given message + diff is a duplicate.
        Returns True if duplicate (should be dropped), False if unique (and now cached).
        """
        content = f"{message}\n{diff}"
        content_bytes = content.encode('utf-8')
        ehash = hashlib.sha256(content_bytes).hexdigest()
        
        if ehash in self.exact_hashes:
            return True
            
        self.exact_hashes.add(ehash)
        
        if self.method != "minhash":
            return False
            
        # MinHash check
        m = MinHash(num_perm=128)
        tokens = content.split()
        if not tokens:
            return False
            
        for token in tokens:
            m.update(token.encode('utf-8'))
            
        # Query LSH
        results = self.lsh.query(m)
        if results:
            return True
            
        # Not duplicate: insert
        self.lsh.insert(record_id, m)
        return False
