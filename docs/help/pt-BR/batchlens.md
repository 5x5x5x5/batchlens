# BatchLens

**Demonstração sintética · não GxP · não usar para controle de processo, liberação ou
disposição de lotes.**

O BatchLens acompanha lotes de anticorpos da cultura de produção até a etapa de captura por
Proteína A e mostra, para cada lote, quanto produto havia em cada ponto e de onde vem cada
número. Todos os lotes aqui são sintéticos: feitos por um gerador, não medidos em planta alguma.

## Lotes

**Lotes** lista cada lote com seu produto, seu biorreator, início e fim, e uma marca no lote de
referência, aquele com que os outros são comparados. Abra um lote pelo seu identificador.

## Um lote

- **O que se sabia em cada momento**: arraste o controle para ver o lote como estava em um
  momento anterior. Tudo abaixo mostra então apenas o que havia sido coletado e reportado até
  ali. Um resultado reportado depois não é usado, mesmo que a amostra seja anterior.
- **Execuções de fase**: o que aconteceu em qual ativo, e quando. Um lote é uma janela em
  equipamento compartilhado: o mesmo biorreator recebe um lote depois do outro.
- **Constatações** (não no lote de referência): onde o título deste lote se afastou do título
  do lote de referência, se isso ocorreu. Uma observação (a primeira amostra abaixo da
  referência além da tolerância e após a qual todas as amostras posteriores ficaram abaixo),
  um cálculo (a massa de produto na colheita em relação à da referência) e nenhuma causa: o
  app não faz diagnóstico. O mesmo vale para cada etapa: um rendimento ou recuperação abaixo
  da referência além da tolerância. Sob um afastamento, os outros resultados das mesmas
  amostras aparecem ao lado dos da referência, para leitura; o app nada conclui deles.
- **Métricas**: cada uma com valor e unidade, estado, os motivos e os identificadores das
  entradas, ao lado do valor do lote de referência e da diferença.
- **Recuperação no downstream**: cada etapa de purificação com a massa de produto que entrou
  e saiu, seu rendimento ao lado do lote de referência e o que resta da colheita. Abaixo,
  cada pool e os pools de que foi formado; onde pools foram combinados, a massa combinada é
  conferida com a soma das partes.
- **Medições de pool**: o volume e a concentração por trás de cada massa de pool.
- **Tendências**: os sinais online do biorreator durante a fase de produção, lidos do
  PlantCraft, e a densidade de células viáveis e o título offline nos instantes de coleta.
- **Amostras**: quando cada uma foi coletada. Se um horário foi registrado errado, um editor
  pode **corrigir o horário**, informando o motivo. O valor registrado é mantido e listado ao
  lado da correção, e o log de auditoria do PlantCraft guarda quem alterou e por quê. Editores
  também podem tornar um lote a referência pelo botão no topo da página.
- **Resultados de ensaio**: cada resultado com dois instantes, quando a amostra foi coletada e
  quando o resultado ficou disponível. Nunca são a mesma coisa.

## Como ler um estado

| Estado | Significado |
|---|---|
| Utilizável | Calculado a partir de entradas válidas |
| Suspeito | Calculado, mas uma entrada ou o resultado é implausível. O valor é mostrado, sinalizado |
| Insuficiente | Não calculado: falta algo necessário ou ainda não está disponível |
| Inválido | Não calculado: uma entrada viola uma regra (unidade errada, valor negativo) |

Uma métrica sem valor sempre diz por quê. Quando o PlantCraft não tem o ativo ou o sinal, o app
diz qual não encontrou em vez de desenhar uma tendência que não tem.

## Perguntar ao assistente

O assistente do PlantCraft pode ler o BatchLens: listar os lotes e ler as métricas, as
constatações e os rendimentos de purificação de um lote, como você (ele vê apenas o que você
pode abrir). Ele recebe os mesmos números desta página, com estados e motivos, e é avisado de
que o BatchLens não atribui causa. Se ele oferecer uma, é inferência do próprio assistente,
não uma constatação do app.

## Bom saber

- As massas são estimativas de concentração vezes volume; o método de ensaio é indicado.
- Unidades nunca são convertidas. Um valor em outra unidade é inválido.
- Os horários são mostrados no fuso da instalação, indicado em cada página.
- As fórmulas, suas premissas e as configurações estão em `docs/scientific-assumptions.md`
  do projeto.
