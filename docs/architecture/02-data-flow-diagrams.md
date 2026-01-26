graph TD
    subgraph "Clinical Environment (Robotics Edge)"
        A[Kinematic Telemetry Sensors] -->|Real-time Stream| B(Agentic Clinical Safety Nodes)
    end

    subgraph "AIOps Platform (Multi-Cloud Control Plane)"
        B -->|gRPC/Protobuf| C{Data Ingestion Layer}
        C --> D[Prometheus/Grafana Metrics]
        
        subgraph "AI Brain (Predictive Engine)"
            C --> E[[LSTM/TCN Inference Model]]
            E --> F{Failure Prediction}
        end
    end

    subgraph "SRE & Resilience (Automated Response)"
        F -->|High Probability Incident| G[ArgoCD/GitOps Re-provisioning]
        F -->|Anomaly Detected| H[Self-Healing Script/Ansible]
        G --> I[Active-Active Failover]
        H --> I
    end

    subgraph "Governance & Compliance"
        I --> J[HIPAA Audit Logs]
        J --> K[Executive Dashboard]
    end

    style E fill:#f9f,stroke:#333,stroke-width:4px
    style I fill:#00ff00,stroke:#333,stroke-width:2px
    style F color:#fff,fill:#ff0000,stroke:#333
