graph TD
    %% Global Styles
    classDef predictive stroke:#f39c12,stroke-width:2px,stroke-dasharray: 5 5;
    classDef infra fill:#2c3e50,color:#fff,stroke:#34495e;
    classDef healthcare fill:#e74c3c,color:#fff,stroke:#c0392b;

    subgraph Edge ["<b>Robotics Edge Layer (Clinical Environment)</b>"]
        A[/"Kinematic Sensors (IoT)"/] --- B("Agentic Safety Node")
    end

    subgraph Platform ["<b>AIOps Control Plane (Multi-Cloud)</b>"]
        B -->|gRPC / TLS 1.3| C{"Data Orchestrator"}
        
        subgraph AI_Engine ["Predictive Intelligence"]
            C --> D[["LSTM/TCN Model"]]
            D --> E{"Risk Scoring"}
        end

        C -.-> F[("Telemetry Store")]
    end

    subgraph Response ["<b>Resilience Engine (SRE)</b>"]
        E -->|Critical| G{{"GitOps (ArgoCD)"}}
        E -->|Warning| H{{"Self-Healing Script"}}
        
        G --> I[<b>Active-Active Failover</b>]
        H --> I
    end

    subgraph Compliance ["<b>Governance & Audit</b>"]
        I --> J["HIPAA / HDS Logs"]
        J --> K["Executive SLM Dashboard"]
    end

    %% Apply Styles
    class D,E predictive;
    class B,A healthcare;
    class G,I,C infra;

    %% Add Legend/Key as a Note
    Note["Predictive Logic (LSTM/TCN) mapped to Clinical Safety SLOs"]
