import sqlfactory

def main():
    sqlfactory = SqlFactory()

    sqlfactory.email_insert('696969', 'gene-test', 'test-contents', 'CURRENT_TIMESTAMP()')

main()