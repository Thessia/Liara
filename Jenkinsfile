pipeline {
    agent {
        docker {
            image 'pandentia/jenkins-discordpy-rewrite'
        }
    }
    stages {
        stage('Dependencies') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }
        stage('Test') {
            steps {
                sh 'cloc .'
                sh 'flake8 --show-source --max-line-length 120 .'
                sh 'python3 -m compileall .'
            }
        }
    }
    post {
        always {
            cleanWs notFailBuild: true
        }
    }
}
