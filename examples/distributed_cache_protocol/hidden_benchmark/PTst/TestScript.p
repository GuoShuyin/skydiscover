test tcTargetedLSI [main = TargetedLSIDriver]:
    assert LSIInvariant in
    {TargetedLSIDriver, StorageCluster, StorageProxy, CacheNode};

test tcBalancedLSI [main = BalancedWorkloadDriver]:
    assert LSIInvariant in
    {BalancedWorkloadDriver, StorageCluster, StorageProxy, CacheNode, BalancedClient};

test tcWriteHeavyLSI [main = WriteHeavyWorkloadDriver]:
    assert LSIInvariant in
    {WriteHeavyWorkloadDriver, StorageCluster, StorageProxy, CacheNode, WriteBiasedClient};

test tcProxyDiscipline [main = ProxyDisciplineDriver]:
    assert LSIInvariant, ProxyQueueDiscipline in
    {ProxyDisciplineDriver, StorageCluster, StorageProxy, CacheNode, ProxyBurstDriverClient};
