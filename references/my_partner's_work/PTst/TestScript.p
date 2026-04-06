// PTst/TestScript.p

test tcOwnershipSafetyLSI [main = TestDriver]:
    assert LSISafety in
    {TestDriver, TiDB, NetworkProxy, CacheNode, AutoSharder, Client};

test tcOwnershipSafetyLSIOnly [main = TestDriver]:
    assert LSISafety in
    {TestDriver, TiDB, NetworkProxy, CacheNode, AutoSharder, Client};

test tcDelayWriteFocused [main = DelayWriteFocusedDriver]:
    assert LSISafety in
    {DelayWriteFocusedDriver, TiDB, NetworkProxy, CacheNode, AutoSharder, WriteHammerClient};

test tcProxyLSI [main = ProxyLSIDriver]:
    assert LSISafety in
    {ProxyLSIDriver, TiDB, NetworkProxy, CacheNode, AutoSharder, WriteHammerClient, ReadHammerClient};
