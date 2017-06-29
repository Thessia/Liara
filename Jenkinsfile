pipeline {
    agent {
        docker {
            image 'pandentia/jenkins-discordpy-rewrite'
            args '-u 0'
        }
    }
    stages {
        stage('Dependencies') {
            steps {
                sh 'pip3 install -r requirements.txt'
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
