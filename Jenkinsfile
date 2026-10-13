// Jenkins pipeline mirroring .github/workflows/ci.yml, stage for stage (python, node, then shell/config;
// each matrix runs its cells in parallel — declarative Jenkins can't nest a matrix inside `parallel`). Use it where the client
// standardises on Jenkins. GitHub Actions stays the source of truth: when a gate changes there,
// change it here in the same PR. Notes and differences: docs/guides/devsecops-integration.md#jenkins
//
// Requirements: a Docker-capable agent (label 'docker'), and these plugins: Pipeline, Docker
// Pipeline, JUnit, Coverage, Workspace Cleanup, Timestamper.
pipeline {
  agent none

  options {
    timestamps()
    timeout(time: 45, unit: 'MINUTES')
    // Equivalent of the workflow's `concurrency: cancel-in-progress`.
    disableConcurrentBuilds(abortPrevious: true)
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }

  environment {
    FORCE_COLOR = '1'
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
  }

  stages {
    stage('python') {
      matrix {
        axes {
          axis {
            name 'PYTHON'
            values '3.11', '3.12'
          }
        }
        agent {
          docker {
            image "python:${PYTHON}-slim"
            label 'docker'
            args '-u root'
          }
        }
        stages {
          stage('Install') {
            steps {
              sh '''
                apt-get update -qq && apt-get install -y -qq --no-install-recommends git > /dev/null
                python -m pip install --upgrade pip
                python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
                python -m pip install -e '.[dev,ml,robotics]'
              '''
            }
          }
          stage('Lint') {
            steps {
              sh 'ruff check src tests && ruff format --check src tests'
            }
          }
          stage('Type check') {
            steps {
              sh 'mypy'
            }
          }
          stage('Test') {
            steps {
              sh 'pytest --cov --cov-report=term --cov-report=xml --junitxml=junit.xml'
            }
            post {
              always {
                junit testResults: 'junit.xml', allowEmptyResults: true
                recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']],
                               qualityGates: [[threshold: 75.0, metric: 'LINE', baseline: 'PROJECT']])
              }
            }
          }
          stage('CLI smoke test') {
            steps {
              sh '''
                golden --version
                golden config show > /dev/null
                golden roi --vertical migration
                golden migrate manifests --output /tmp/waves
                golden gpu analyze --scenario hot > /dev/null
                golden demo client --vertical all --client "CI" --fast --output /tmp/demo > /dev/null
                golden demo engine --epochs 1 --output-dir /tmp/engine > /dev/null
                golden iam model > /dev/null
                golden iam multicloud > /dev/null
                golden network verify > /dev/null
                golden finops report > /dev/null
                golden db explain --scenario healthy > /dev/null
                golden migrate portfolio > /dev/null
                golden features demo > /dev/null
              '''
            }
          }
          stage('Agent-ops gates') {
            environment {
              GOLDEN_AGENTOPS_DIR = '/tmp/agentops'
            }
            steps {
              sh '''
                golden agent verify > /tmp/agent-verify.json
                golden agent redteam > /tmp/redteam.json
                golden model retrain --force --registry /tmp/registry > /tmp/retrain.json
                golden rag ask "How long are PHI audit logs retained?" > /dev/null
              '''
            }
          }
        }
        post {
          always {
            cleanWs()
          }
        }
      }
    }

    stage('node') {
      matrix {
        axes {
          axis {
            name 'APP'
            values 'client-portal', 'workload'
          }
        }
        agent {
          docker {
            image 'node:22-slim'
            label 'docker'
          }
        }
        stages {
          stage('Lint and test') {
            steps {
              dir("apps/${APP}") {
                sh 'npm ci && npm run lint && npm test'
              }
            }
          }
        }
        post {
          always {
            cleanWs()
          }
        }
      }
    }

    stage('shell, compose & config') {
      agent {
        label 'docker'   // runs on the host: needs the docker CLI for `docker compose config`
      }
      stages {
        stage('ShellCheck') {
          steps {
            sh '''
              git ls-files '*.sh' ':!:deploy/terraform/**' \
                | xargs docker run --rm -v "$PWD:/mnt" -w /mnt koalaman/shellcheck:v0.10.0 -S warning
            '''
          }
        }
        stage('Compose files are valid') {
          steps {
            sh '''
              docker compose config -q
              docker compose --profile robotics config -q
              docker compose -f observability/docker-compose.yml config -q
            '''
          }
        }
        stage('YAML & JSON parse') {
          steps {
            sh 'docker run --rm -v "$PWD:/repo" -w /repo python:3.12-slim sh -c "apt-get update -qq && apt-get install -y -qq git >/dev/null && git config --global --add safe.directory /repo && pip install -q pyyaml && python3 scripts/ci/check-yaml-json.py"'
          }
        }
        stage('Ansible baseline') {
          steps {
            sh '''
              docker run --rm -v "$PWD/deploy/ansible:/work" -w /work python:3.12-slim sh -c '
                pip install -q ansible-core ansible-lint &&
                ansible-galaxy collection install -r requirements.yml > /dev/null &&
                ANSIBLE_CONFIG=ansible.cfg ansible-playbook --syntax-check playbooks/baseline.yml &&
                ANSIBLE_CONFIG=ansible.cfg ansible-lint playbooks/baseline.yml roles/'
            '''
          }
        }
      }
      post {
        always {
          cleanWs()
        }
      }
    }
  }
}
